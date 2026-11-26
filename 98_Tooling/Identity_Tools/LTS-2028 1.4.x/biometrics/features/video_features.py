"""
File: biometrics/features/video_features.py

Purpose
-------
Turn a grayscale video clip into a fixed-length appearance template and score
how closely two such templates resemble each other.

Public interface:
- class VideoFeatureError(ValueError) -- Raised when a clip or a feature
  vector cannot be processed.
- extract_from_frames(width, height, frames) -- Template from decoded frames
  (each frame is ``width * height`` grayscale bytes).
- extract_from_video(path) -- Decode a BRVID file with ``codecs.video`` and
  extract.
- compare(vector_a, vector_b) -- Similarity in (0.0, 1.0] between two templates.
- FEATURE_VECTOR_LENGTH -- Number of values in every video template.

The template is an illumination-normalised picture of the scene, not a
brightness summary. Every sampled frame is reduced to a 48 x 48 block-mean
image and then passed through a Tan-Triggs style preprocessing chain: gamma
compression (so a lighting gain becomes an additive offset), a
difference-of-Gaussians band-pass (so slowly varying shading from a
directional light, and fine sensor noise, are both removed), and contrast
equalisation with a soft tanh limit (so overall exposure no longer matters).
The processed frame is pooled to 24 x 24 and the per-pixel temporal median over
the sampled frames is the template. The median discards transient content: a
blink, a hand passing in front of the lens, or a few corrupted frames.

compare() slides one template over the other by up to SHIFT_CELLS cells in
each direction so that a small change in head position or camera framing does
not count against the match, takes the root-mean-square difference over the
overlapping area, and maps it through exp(-distance / DISTANCE_SCALE). The
scale is chosen so that the package's default video threshold (0.75, see
biometrics/engine/modalities.py) sits at roughly a 1% impostor-acceptance
operating point on the development clips the extractor was tuned on.

Motion is deliberately not part of the template. How a person moves differs
from one recording to the next and says nothing about who they are; whether
the motion is that of a live subject is the job of biometrics/features/
liveness.py.

Communication / relationships
-----------------------------
Depends on (project modules):
- biometrics.codecs.image_tools (block-mean reduction and nearest-neighbour
  resizing)
- biometrics.codecs.video (BRVID decoding)
Standard library: math.
Imported by:
- biometrics/engine/modalities.py (registers extract_from_video and compare)
Covered by tests: biometrics/tests/test_video_features.py,
biometrics/tests/test_video_support.py,
biometrics/tests/test_multimodal_flow.py.

Settings / parameters
---------------------
- ANALYSIS_SIZE = 48 -- Side of the square image each frame is reduced to.
- TEMPLATE_SIZE = 24 -- Side of the pooled template image.
- GAMMA = 0.2 -- Exponent of the gamma compression.
- SIGMA_FINE = 1.5 / SIGMA_COARSE = 4.0 -- Gaussian widths (in analysis
  pixels) of the band-pass; their difference is the filtered image.
- TANH_GAIN = 1.0 -- Strength of the soft limit applied after equalisation.
- MIN_DETAIL = 1e-4 -- Band-passed RMS below which a frame has no detail.
- SHIFT_CELLS = 3 -- Largest horizontal and vertical offset tried in compare().
- MAX_FRAMES_SAMPLED = 12 -- Longer clips are evenly subsampled to this many
  frames, which bounds the cost of extraction.
- DISTANCE_SCALE -- RMS difference that maps to a score of exp(-1).
- FEATURE_VECTOR_LENGTH = TEMPLATE_SIZE * TEMPLATE_SIZE = 576

Edge cases
----------
- extract_from_frames() raises VideoFeatureError: "width and height must be
  positive." for non-integer, boolean, zero or negative dimensions;
  "at least one frame is required." for an empty clip; "frame {index} does
  not match the given dimensions." for a frame of the wrong length.
- extract_from_frames() raises VideoFeatureError: "video contains no usable
  spatial detail." when every sampled frame is uniform, so a black, white or
  frozen-blank capture cannot be enrolled.
- Frames smaller than ANALYSIS_SIZE in either direction are enlarged by
  nearest-neighbour sampling first; non-square frames are stretched to the
  square analysis image, which is consistent for a given camera.
- compare() raises VideoFeatureError: "feature vectors must be the same
  length." when the lengths differ, which is how a template created by an
  earlier extractor is detected; the owner must re-enrol. Non-finite values
  score 0.0.

Known limitations
-----------------
- This is an image-appearance template of whatever the camera sees, not a
  face-recognition model. It does not detect or align faces, so the subject
  must be framed consistently between enrolment and verification, within
  SHIFT_CELLS of translation. Large rotations, scale changes, glasses or a
  change of hairstyle or background reduce the score.
- Strong lighting changes are tolerated, but extreme exposure (heavily clipped
  highlights or deep shadow with no detail) removes the structure the
  template relies on.
- Pooling to 24 x 24 means fine facial detail is not used; the template
  describes coarse layout and contrast.
- It does not establish that a live person is present. A photograph or a
  replayed recording produces a matching template; see liveness.py.
- DISTANCE_SCALE was calibrated on synthetic development clips. It must be
  re-checked against clips from the real capture device before the default
  threshold is relied upon.

Examples
--------
Call shapes only, not a runnable script: width, height, frames and path stand
for values the caller supplies.

::

    from biometrics.features.video_features import (
        extract_from_frames,
        extract_from_video,
        compare,
    )
    template = extract_from_frames(width, height, frames)
    probe = extract_from_video(path)
    score = compare(template, probe)
"""
import math

from biometrics.codecs import image_tools, video

ANALYSIS_SIZE = 48
TEMPLATE_SIZE = 24
GAMMA = 0.2
SIGMA_FINE = 1.5
SIGMA_COARSE = 4.0
TANH_GAIN = 1.0
MIN_DETAIL = 1e-4
SHIFT_CELLS = 3
MAX_FRAMES_SAMPLED = 12  # bounds extraction cost for a very long capture;
# frames beyond this are evenly subsampled rather than all processed.
DISTANCE_SCALE = 0.55
FEATURE_VECTOR_LENGTH = TEMPLATE_SIZE * TEMPLATE_SIZE


class VideoFeatureError(ValueError):
    """Raised when video feature extraction or comparison cannot proceed."""


def _subsample(frames: list) -> list:
    if len(frames) <= MAX_FRAMES_SAMPLED:
        return frames
    step = len(frames) / MAX_FRAMES_SAMPLED
    indices = sorted({int(index * step) for index in range(MAX_FRAMES_SAMPLED)})
    return [frames[index] for index in indices]


def _kernel(sigma: float) -> list:
    radius = max(1, int(math.ceil(2.5 * sigma)))
    weights = [math.exp(-(offset * offset) / (2.0 * sigma * sigma))
               for offset in range(-radius, radius + 1)]
    total = sum(weights)
    return [weight / total for weight in weights]


_FINE = _kernel(SIGMA_FINE)
_COARSE = _kernel(SIGMA_COARSE)


def _blur_line(line: list, kernel: list) -> list:
    """1-D convolution with reflected borders."""
    radius = len(kernel) // 2
    size = len(line)
    padded = ([line[min(size - 1, radius - i)] for i in range(radius)] + line +
              [line[max(0, size - 2 - i)] for i in range(radius)])
    out = [0.0] * size
    for tap, weight in enumerate(kernel):
        out = [o + weight * v for o, v in zip(out, padded[tap:tap + size])]
    return out


def _blur(rows: list, kernel: list) -> list:
    """Separable Gaussian blur of a list of equal-length rows."""
    horizontal = [_blur_line(row, kernel) for row in rows]
    columns = [_blur_line(list(column), kernel) for column in zip(*horizontal)]
    return [list(row) for row in zip(*columns)]


def _analysis_image(width: int, height: int, frame: bytes) -> list:
    """Block-mean reduce a frame to ANALYSIS_SIZE x ANALYSIS_SIZE rows."""
    if width < ANALYSIS_SIZE or height < ANALYSIS_SIZE:
        new_width, new_height = max(width, ANALYSIS_SIZE), max(height, ANALYSIS_SIZE)
        frame = image_tools.resize_nearest(width, height, frame, new_width, new_height)
        width, height = new_width, new_height
    means = image_tools.block_grid_means(width, height, frame, ANALYSIS_SIZE)
    return [means[row * ANALYSIS_SIZE:(row + 1) * ANALYSIS_SIZE]
            for row in range(ANALYSIS_SIZE)]


def _process_frame(width: int, height: int, frame: bytes):
    """Illumination-normalised TEMPLATE_SIZE x TEMPLATE_SIZE image, or None."""
    rows = _analysis_image(width, height, frame)
    rows = [[(value + 1.0) ** GAMMA for value in row] for row in rows]
    fine, coarse = _blur(rows, _FINE), _blur(rows, _COARSE)
    band = [[a - b for a, b in zip(fr, cr)] for fr, cr in zip(fine, coarse)]
    energy = sum(v * v for row in band for v in row) / (ANALYSIS_SIZE * ANALYSIS_SIZE)
    rms = math.sqrt(energy)
    if rms < MIN_DETAIL:
        return None
    pooled = []
    for r in range(0, ANALYSIS_SIZE, 2):
        top, bottom = band[r], band[r + 1]
        pooled.extend(math.tanh(TANH_GAIN * 0.25 * (top[c] + top[c + 1] +
                                                    bottom[c] + bottom[c + 1]) / rms)
                      for c in range(0, ANALYSIS_SIZE, 2))
    return pooled


def extract_from_frames(width: int, height: int, frames: list) -> list:
    """Extract the fixed-length appearance template from grayscale frames."""
    if (isinstance(width, bool) or isinstance(height, bool)
            or not isinstance(width, int) or not isinstance(height, int)
            or width <= 0 or height <= 0):
        raise VideoFeatureError("width and height must be positive.")
    if not frames:
        raise VideoFeatureError("at least one frame is required.")
    for index, frame in enumerate(frames):
        if len(frame) != width * height:
            raise VideoFeatureError(
                f"frame {index} does not match the given dimensions."
            )
    processed = []
    for frame in _subsample(frames):
        result = _process_frame(width, height, frame)
        if result is not None:
            processed.append(result)
    if not processed:
        raise VideoFeatureError("video contains no usable spatial detail.")
    middle = len(processed) // 2
    template = []
    for column in zip(*processed):
        ordered = sorted(column)
        if len(ordered) % 2:
            template.append(ordered[middle])
        else:
            template.append(0.5 * (ordered[middle - 1] + ordered[middle]))
    return template


def extract_from_video(path) -> list:
    """Read a BRVID file and extract its fixed-length video feature vector."""
    decoded = video.read_video(path)
    return extract_from_frames(decoded["width"], decoded["height"], decoded["frames"])


def compare(vector_a: list, vector_b: list) -> float:
    """Similarity in (0.0, 1.0] between two video templates.

    The templates are slid over each other by up to SHIFT_CELLS cells and the
    smallest root-mean-square difference over the overlap is mapped through
    exp(-d / DISTANCE_SCALE). Identical templates score exactly 1.0. Malformed
    or non-finite vectors score 0.0, so they can never produce a match.
    """
    if len(vector_a) != len(vector_b):
        raise VideoFeatureError("feature vectors must be the same length.")
    if not vector_a:
        return 0.0
    try:
        a = [float(v) for v in vector_a]
        b = [float(v) for v in vector_b]
    except (TypeError, ValueError, OverflowError):
        return 0.0
    if not all(math.isfinite(v) for v in a + b):
        return 0.0
    if len(a) != FEATURE_VECTOR_LENGTH:
        return math.exp(-math.dist(a, b) / math.sqrt(len(a)) / DISTANCE_SCALE)
    size = TEMPLATE_SIZE
    rows_a = [a[r * size:(r + 1) * size] for r in range(size)]
    rows_b = [b[r * size:(r + 1) * size] for r in range(size)]
    best = None
    for dy in range(-SHIFT_CELLS, SHIFT_CELLS + 1):
        for dx in range(-SHIFT_CELLS, SHIFT_CELLS + 1):
            ax0, bx0 = max(0, dx), max(0, -dx)
            width = size - abs(dx)
            total = 0.0
            for r in range(max(0, dy), size + min(0, dy)):
                row_a = rows_a[r][ax0:ax0 + width]
                row_b = rows_b[r - dy][bx0:bx0 + width]
                total += sum((x - y) * (x - y) for x, y in zip(row_a, row_b))
            area = width * (size - abs(dy))
            distance = math.sqrt(total / area)
            if best is None or distance < best:
                best = distance
    return math.exp(-best / DISTANCE_SCALE)
