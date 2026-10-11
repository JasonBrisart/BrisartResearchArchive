"""
File: biometrics/codecs/video.py

Purpose
-------
A minimal, custom frame-sequence container for the video modality.

Public interface:
- class VideoFormatError(ValueError) -- Raised when data does not parse as a
  well-formed BRVID container.
- encode(width, height, frame_rate, frames) -- Serialise a list of equal-sized
  grayscale frames into BRVID bytes.
- decode(data) -- Parse BRVID bytes into ``{"width", "height", "frame_rate",
  "frames"}``.
- probe(path) -- Read only the header, returning metadata without loading frame
  data.
- read_video(path) -- Read and decode a BRVID file from disk.
- write_video(path, width, height, frame_rate, frames) -- Encode and write a
  list of grayscale frames as a BRVID file.

Design notes:

There is no dependency on a real video codec here (no H.264, no container
muxer, no third-party library) because none is needed: video enrollment is a
short sequence of grayscale frames captured or generated for a single identity,
not general-purpose video playback. This module defines the smallest format
that can hold that: a fixed header followed by concatenated raw grayscale
frames, each exactly ``width * height`` bytes, with no per-frame compression.

Format layout::

    offset  size  field
    0       8     magic: the ASCII bytes BRVID001 (the version is in the magic)
    8       4     width, unsigned 32-bit, big-endian
    12      4     height, unsigned 32-bit, big-endian
    16      4     frame_count, unsigned 32-bit, big-endian
    20      4     frame_rate, unsigned 32-bit, big-endian
    24      body  frame_count blocks of width x height bytes: 8-bit grayscale,
                  row-major, one block after another, no compression

Communication / relationships
-----------------------------
Standard library: pathlib, struct.
Imported by:
- biometrics/app.py
- biometrics/engine/enrollment.py
- biometrics/engine/verification.py
- biometrics/features/video_features.py
- biometrics/samples/sample_generator.py
Covered by tests: biometrics/tests/test_liveness.py,
biometrics/tests/test_video_support.py.

Settings / parameters
---------------------
- MAGIC = b"BRVID001"
- HEADER_STRUCT = struct.Struct(">8sIIII")
- MAX_DIMENSION = 8192
- MAX_FRAME_COUNT = 100_000 -- generous ceiling; guards a corrupt header from
  driving an unbounded read.
- MAX_BODY_BYTES = 512 * 1024 * 1024 -- overall ceiling on the concatenated
  frame body. width, height, and frame_count are each individually bounded
  above, but their PRODUCT was not, so a header sitting at each individual
  maximum implied a body far larger than any real clip and forced a large slice
  allocation before the length mismatch could even be detected.

Edge cases
----------
- encode() raises VideoFormatError: "width and height must be positive."
- encode() raises VideoFormatError: "width or height exceeds the supported
  maximum."
- encode() raises VideoFormatError: "frame_rate must be positive."
- encode() raises VideoFormatError: "at least one frame is required."
- encode() raises VideoFormatError: "frame count exceeds the supported maximum
  of {...}."
- encode() raises VideoFormatError: "frame {...} is not bytes."
- encode() raises VideoFormatError: "frame {...} has {...} bytes, expected
  {...}."
- decode() raises VideoFormatError: "video data must be bytes."
- decode() raises VideoFormatError: "data is too short to contain a valid
  header."
- decode() raises VideoFormatError: "not a BRVID container (bad magic)."
- decode() raises VideoFormatError: "width and height must be positive."
- decode() raises VideoFormatError: "width or height exceeds the supported
  maximum."
- decode() raises VideoFormatError: "frame_count must be positive."
- decode() raises VideoFormatError: "frame count exceeds the supported maximum
  of {...}."
- decode() raises VideoFormatError: "frame_rate must be positive."
- decode() raises VideoFormatError: "frame_count * width * height exceeds the
  supported body-size ceiling."
- decode() raises VideoFormatError: "expected {...} bytes of frame data, found
  {...}."
- probe() raises VideoFormatError: "data is too short to contain a valid
  header."
- probe() raises VideoFormatError: "not a BRVID container (bad magic)."
- probe() raises VideoFormatError: "width and height must be positive."
- probe() raises VideoFormatError: "width or height exceeds the supported
  maximum."
- probe() raises VideoFormatError: "frame_count must be positive."
- probe() raises VideoFormatError: "frame count exceeds the supported maximum
  of {...}."
- probe() raises VideoFormatError: "frame_rate must be positive."
- probe() raises VideoFormatError: "frame_count * width * height exceeds the
  supported body-size ceiling."

Known limitations
-----------------
- Uncompressed and grayscale only. A file is the 24-byte header plus
  frame_count x width x height bytes, so size grows fast: a one-minute 640 x
  480 clip at 30 fps is about 553 MB, which is above MAX_BODY_BYTES (512 MiB)
  and would be refused by decode().
- encode() and decode() disagree about the body-size ceiling. encode() checks
  the dimensions and frame count but not MAX_BODY_BYTES, so it can write a file
  that decode() and read_video() then reject.
- Custom format, readable only by this project. The repository contains no
  converter from common video formats, so real footage must be converted to
  8-bit grayscale BRVID frames by other means.
- frame_rate is a positive whole number stored as an unsigned 32-bit integer,
  so rates such as 29.97 cannot be represented. There are no per-frame
  timestamps and no audio.
- probe() reads only the header and does not validate the body. For a truncated
  file it returns metadata with size_matches_header set to False instead of
  raising; read_video() and decode() raise VideoFormatError.

Examples
--------
Run from the repository root.

::

    import tempfile
    from pathlib import Path

    from biometrics.codecs.video import probe, read_video, write_video

    width, height = 8, 8
    frames = []
    for step in range(5):
        frames.append(bytes((x + y + step * 10) % 256
                            for y in range(height) for x in range(width)))

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "clip.brvid"
        write_video(path, width, height, 5, frames)    # frame_rate is whole
        print(probe(path))                             # header only
        clip = read_video(path)

    print(clip["width"], clip["height"], clip["frame_rate"])
    print(len(clip["frames"]))
"""

import struct
from pathlib import Path

MAGIC = b"BRVID001"
HEADER_STRUCT = struct.Struct(">8sIIII")
MAX_DIMENSION = 8192
MAX_FRAME_COUNT = 100_000  # generous ceiling; guards a corrupt header from
# driving an unbounded read.
MAX_BODY_BYTES = 512 * 1024 * 1024  # overall ceiling on the concatenated frame
# body. width, height, and frame_count are each individually bounded above,
# but their PRODUCT was not, so a header sitting at each individual maximum
# implied a body far larger than any real clip and forced a large slice
# allocation before the length mismatch could even be detected.


class VideoFormatError(ValueError):
    """Raised when data does not parse as a well-formed BRVID container."""


def encode(width: int, height: int, frame_rate: int, frames: list) -> bytes:
    """Serialise a list of equal-sized grayscale frames into BRVID bytes."""
    if width <= 0 or height <= 0:
        raise VideoFormatError("width and height must be positive.")
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise VideoFormatError("width or height exceeds the supported maximum.")
    if frame_rate <= 0:
        raise VideoFormatError("frame_rate must be positive.")
    if not frames:
        raise VideoFormatError("at least one frame is required.")
    if len(frames) > MAX_FRAME_COUNT:
        raise VideoFormatError(
            f"frame count exceeds the supported maximum of {MAX_FRAME_COUNT}."
        )
    frame_bytes = width * height
    body = bytearray()
    for index, frame in enumerate(frames):
        if not isinstance(frame, (bytes, bytearray)):
            raise VideoFormatError(f"frame {index} is not bytes.")
        if len(frame) != frame_bytes:
            raise VideoFormatError(
                f"frame {index} has {len(frame)} bytes, expected {frame_bytes}."
            )
        body += frame
    header = HEADER_STRUCT.pack(MAGIC, width, height, len(frames), frame_rate)
    return header + bytes(body)


def decode(data: bytes) -> dict:
    """Parse BRVID bytes into ``{"width", "height", "frame_rate", "frames"}``.

    ``frames`` is a list of flat grayscale ``bytes`` objects, one per frame.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise VideoFormatError("video data must be bytes.")
    data = bytes(data)
    if len(data) < HEADER_STRUCT.size:
        raise VideoFormatError("data is too short to contain a valid header.")
    magic, width, height, frame_count, frame_rate = HEADER_STRUCT.unpack(
        data[:HEADER_STRUCT.size]
    )
    if magic != MAGIC:
        raise VideoFormatError("not a BRVID container (bad magic).")
    if width <= 0 or height <= 0:
        raise VideoFormatError("width and height must be positive.")
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise VideoFormatError("width or height exceeds the supported maximum.")
    if frame_count <= 0:
        raise VideoFormatError("frame_count must be positive.")
    if frame_count > MAX_FRAME_COUNT:
        raise VideoFormatError(
            f"frame count exceeds the supported maximum of {MAX_FRAME_COUNT}."
        )
    if frame_rate <= 0:
        raise VideoFormatError("frame_rate must be positive.")
    frame_bytes = width * height
    expected_body = frame_count * frame_bytes
    # Fix 1 (2026-09-09): bound frame_count * width * height BEFORE slicing the
    # body, so a header whose fields are each individually valid cannot
    # multiply into an absurd expected-body size and force a large allocation
    # before the length mismatch below is reached.
    if expected_body > MAX_BODY_BYTES:
        raise VideoFormatError(
            "frame_count * width * height exceeds the supported body-size ceiling."
        )
    body = data[HEADER_STRUCT.size:]
    if len(body) != expected_body:
        raise VideoFormatError(
            f"expected {expected_body} bytes of frame data, found {len(body)}."
        )
    frames = [
        body[index * frame_bytes:(index + 1) * frame_bytes]
        for index in range(frame_count)
    ]
    return {
        "width": width,
        "height": height,
        "frame_rate": frame_rate,
        "frames": frames,
    }


def probe(path) -> dict:
    """Read only the header, returning metadata without loading frame data.

    Used by ``biometrics.app``'s "probe" command so inspecting a large capture
    does not require reading the whole file into memory.
    """
    resolved = Path(path)
    with open(resolved, "rb") as handle:
        header_bytes = handle.read(HEADER_STRUCT.size)
    if len(header_bytes) != HEADER_STRUCT.size:
        raise VideoFormatError("data is too short to contain a valid header.")
    magic, width, height, frame_count, frame_rate = HEADER_STRUCT.unpack(header_bytes)
    if magic != MAGIC:
        raise VideoFormatError("not a BRVID container (bad magic).")
    if width <= 0 or height <= 0:
        raise VideoFormatError("width and height must be positive.")
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise VideoFormatError("width or height exceeds the supported maximum.")
    if frame_count <= 0:
        raise VideoFormatError("frame_count must be positive.")
    if frame_count > MAX_FRAME_COUNT:
        raise VideoFormatError(
            f"frame count exceeds the supported maximum of {MAX_FRAME_COUNT}."
        )
    if frame_rate <= 0:
        raise VideoFormatError("frame_rate must be positive.")
    # Fix 2 (2026-09-11): apply the same frame_count * width * height ceiling
    # decode() gained in 1.3.3 (Fix 1 above), so probe() and decode() agree on
    # what a well-formed header is rather than probe() silently accepting a
    # header decode() would refuse.
    if frame_count * width * height > MAX_BODY_BYTES:
        raise VideoFormatError(
            "frame_count * width * height exceeds the supported body-size ceiling."
        )
    file_size = resolved.stat().st_size
    expected_size = HEADER_STRUCT.size + frame_count * width * height
    return {
        "path": str(resolved),
        "width": width,
        "height": height,
        "frame_count": frame_count,
        "frame_rate": frame_rate,
        "file_size_bytes": file_size,
        "size_matches_header": file_size == expected_size,
    }


def read_video(path) -> dict:
    """Read and decode a BRVID file from disk."""
    with open(path, "rb") as handle:
        return decode(handle.read())


def write_video(path, width: int, height: int, frame_rate: int, frames: list) -> None:
    """Encode and write a list of grayscale frames as a BRVID file."""
    encoded = encode(width, height, frame_rate, frames)
    with open(path, "wb") as handle:
        handle.write(encoded)




