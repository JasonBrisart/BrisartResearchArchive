"""
File: biometrics/codecs/pgm.py

Purpose
-------
Binary PGM (Netpbm P5) reader and writer.

Public interface:
- class PgmFormatError(ValueError) -- Raised when data does not parse as a
  well-formed binary PGM file.
- decode(data) -- Parse binary PGM bytes into ``{"width", "height", "maxval",
  "pixels"}``.
- encode(width, height, pixels, maxval=MAX_MAXVAL) -- Serialise grayscale pixel
  data into binary PGM bytes.
- read_pgm(path) -- Read and decode a binary PGM file from disk.
- write_pgm(path, width, height, pixels, maxval=MAX_MAXVAL) -- Encode and write
  grayscale pixel data as a binary PGM file.

Design notes:

PGM is used as this project's canonical still-image interchange format because
the format itself is a handful of ASCII header tokens followed by a flat run of
raw grayscale bytes -- nothing to parse that requires a dependency, and nothing
lossy or compressed to get subtly wrong. ``png.py`` exists for smaller-on-disk
storage; ``pgm.py`` exists as the format every other codec and feature
extractor can assume without ambiguity.

Communication / relationships
-----------------------------
Standard library: none.
Imported by:
- biometrics/codecs/image_loader.py
- biometrics/samples/sample_generator.py
Covered by tests: biometrics/tests/test_codec_and_dsp_support.py.

Settings / parameters
---------------------
- MAGIC_BINARY_GRAYSCALE = b"P5"
- MAX_MAXVAL = 255
- MAX_DIMENSION = 8192 -- generous ceiling; guards against a corrupt header
  driving an absurd allocation.

Edge cases
----------
- _read_token() raises PgmFormatError: "unexpected end of header while reading
  a token."
- _read_int_token() raises PgmFormatError: "{...} is not a valid integer."
- decode() raises PgmFormatError: "PGM data must be bytes."
- decode() raises PgmFormatError: "not a binary PGM (P5) file."
- decode() raises PgmFormatError: "width and height must be positive."
- decode() raises PgmFormatError: "width or height exceeds the supported
  maximum."
- decode() raises PgmFormatError: "only 8-bit PGM (maxval 1-255) is supported."
- decode() raises PgmFormatError: "missing whitespace separator after maxval."
- decode() raises PgmFormatError: "expected {...} pixel bytes, found {...}."
- encode() raises PgmFormatError: "width and height must be positive."
- encode() raises PgmFormatError: "width or height exceeds the supported
  maximum."
- encode() raises PgmFormatError: "only 8-bit PGM (maxval 1-255) is supported."
- encode() raises PgmFormatError: "pixels must be bytes."
- encode() raises PgmFormatError: "expected {...} pixel bytes, got {...}."
- _read_int_token(): translates ValueError into PgmFormatError; other exceptions may still propagate.

Known limitations
-----------------
- Only 8-bit grayscale (maxval <= 255) is supported.
- There is no use for 16-bit imagery here, and supporting it would double the
  surface area of this parser for a case that never occurs in practice.

Examples
--------
Run from the repository root.

::

    import tempfile
    from pathlib import Path

    from biometrics.codecs.pgm import decode, encode, read_pgm, write_pgm

    width, height = 4, 3
    pixels = bytes(range(width * height))

    data = encode(width, height, pixels)           # binary P5 bytes
    image = decode(data)
    print(image["width"], image["height"], image["maxval"])
    print(image["pixels"] == pixels)

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "sample.pgm"
        write_pgm(path, width, height, pixels)
        print(read_pgm(path)["pixels"] == pixels)
"""

MAGIC_BINARY_GRAYSCALE = b"P5"
MAX_MAXVAL = 255
MAX_DIMENSION = 8192  # generous ceiling; guards against a corrupt header
# driving an absurd allocation.


class PgmFormatError(ValueError):
    """Raised when data does not parse as a well-formed binary PGM file."""


def _skip_whitespace_and_comments(data: bytes, offset: int) -> int:
    length = len(data)
    while offset < length:
        byte = data[offset:offset + 1]
        if byte in b" \t\r\n":
            offset += 1
            continue
        if byte == b"#":
            newline = data.find(b"\n", offset)
            if newline == -1:
                return length
            offset = newline + 1
            continue
        break
    return offset


def _read_token(data: bytes, offset: int) -> tuple:
    offset = _skip_whitespace_and_comments(data, offset)
    start = offset
    length = len(data)
    while offset < length and data[offset:offset + 1] not in b" \t\r\n#":
        offset += 1
    if start == offset:
        raise PgmFormatError("unexpected end of header while reading a token.")
    return data[start:offset], offset


def _read_int_token(data: bytes, offset: int, name: str) -> tuple:
    token, offset = _read_token(data, offset)
    try:
        value = int(token)
    except ValueError as exc:
        raise PgmFormatError(f"{name} is not a valid integer.") from exc
    return value, offset


def decode(data: bytes) -> dict:
    """Parse binary PGM bytes into ``{"width", "height", "maxval", "pixels"}``.

    ``pixels`` is a flat ``bytes`` object of ``width * height`` grayscale
    samples, row-major, top row first.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise PgmFormatError("PGM data must be bytes.")
    data = bytes(data)
    if not data.startswith(MAGIC_BINARY_GRAYSCALE):
        raise PgmFormatError("not a binary PGM (P5) file.")
    offset = len(MAGIC_BINARY_GRAYSCALE)
    width, offset = _read_int_token(data, offset, "width")
    height, offset = _read_int_token(data, offset, "height")
    maxval, offset = _read_int_token(data, offset, "maxval")
    if width <= 0 or height <= 0:
        raise PgmFormatError("width and height must be positive.")
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise PgmFormatError("width or height exceeds the supported maximum.")
    if maxval <= 0 or maxval > MAX_MAXVAL:
        raise PgmFormatError("only 8-bit PGM (maxval 1-255) is supported.")
    # Exactly one whitespace byte separates maxval from the pixel data.
    if offset >= len(data) or data[offset:offset + 1] not in b" \t\r\n":
        raise PgmFormatError("missing whitespace separator after maxval.")
    offset += 1
    expected_bytes = width * height
    pixels = data[offset:offset + expected_bytes]
    if len(pixels) != expected_bytes:
        raise PgmFormatError(
            f"expected {expected_bytes} pixel bytes, found {len(pixels)}."
        )
    return {"width": width, "height": height, "maxval": maxval, "pixels": pixels}


def encode(width: int, height: int, pixels: bytes, maxval: int = MAX_MAXVAL) -> bytes:
    """Serialise grayscale pixel data into binary PGM bytes."""
    if width <= 0 or height <= 0:
        raise PgmFormatError("width and height must be positive.")
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise PgmFormatError("width or height exceeds the supported maximum.")
    if maxval <= 0 or maxval > MAX_MAXVAL:
        raise PgmFormatError("only 8-bit PGM (maxval 1-255) is supported.")
    if not isinstance(pixels, (bytes, bytearray)):
        raise PgmFormatError("pixels must be bytes.")
    expected_bytes = width * height
    if len(pixels) != expected_bytes:
        raise PgmFormatError(
            f"expected {expected_bytes} pixel bytes, got {len(pixels)}."
        )
    header = f"P5\n{width} {height}\n{maxval}\n".encode("ascii")
    return header + bytes(pixels)


def read_pgm(path) -> dict:
    """Read and decode a binary PGM file from disk."""
    with open(path, "rb") as handle:
        return decode(handle.read())


def write_pgm(path, width: int, height: int, pixels: bytes, maxval: int = MAX_MAXVAL) -> None:
    """Encode and write grayscale pixel data as a binary PGM file."""
    encoded = encode(width, height, pixels, maxval)
    with open(path, "wb") as handle:
        handle.write(encoded)




