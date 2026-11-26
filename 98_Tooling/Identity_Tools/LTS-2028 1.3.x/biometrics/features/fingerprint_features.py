"""
File: biometrics/features/fingerprint_features.py

Purpose
-------
Turn a grayscale fingerprint image into a fixed-length ridge-flow template and
score how closely two such templates resemble each other, tolerating the
rotation and finger-placement differences that occur between impressions.

Public interface:
- class FingerprintFeatureError(ValueError) -- Raised when an image or a
  feature vector cannot be processed.
- extract_from_pixels(width, height, pixels) -- Template from decoded
  grayscale pixels (``width * height`` bytes).
- extract_from_image(path) -- Decode an image file with ``image_loader`` and
  extract.
- compare(vector_a, vector_b) -- Similarity in [0.0, 1.0] between two templates.
- TARGET_WIDTH / TARGET_HEIGHT / GRID_SIZE / FEATURE_VECTOR_LENGTH -- The
  analysis resolution and the template layout.

The template describes the direction of the ridges across the print, not the
brightness of the image. The image is resized to 128 x 128 and locally
normalised (each pixel is expressed relative to the mean and spread of its own
17 x 17 neighbourhood, so a faint, dry or over-inked impression has the same
scale as a good one). It is lightly smoothed, and the intensity gradients are
accumulated over 8 x 8 pixel blocks into a structure tensor, which is pooled
with the eight surrounding blocks to be robust to local noise. Each of the
16 x 16 cells then stores two numbers, ``(cos 2t, sin 2t)`` of the dominant
ridge orientation ``t``, scaled by how coherent the ridges are in that cell.
A blank, smudged or noisy cell therefore has a short vector and carries little
weight, while a clear cell carries a unit vector.

compare() looks for the rotation and shift that best align the probe's flow
field with the enrolled one, and scores the aligned overlap as the
coherence-weighted mean of cos(2 * angle difference) between the two ridge
directions. The search runs in two stages: a coarse pass over a full circle in
15-degree steps and one cell of shift on a 8 x 8 pooled field, then a fine
pass (3-degree steps within 7.5 degrees, and two cells of shift) on the full
field around the best few coarse candidates. The raw agreement is mapped
through a power so that the package's default fingerprint threshold (0.80,
see biometrics/engine/modalities.py) sits at roughly a 1% impostor-acceptance
operating point on the development impressions the matcher was tuned on.

Communication / relationships
-----------------------------
Depends on (project modules):
- biometrics.codecs.image_loader (image decoding)
- biometrics.codecs.image_tools (nearest-neighbour resizing)
Standard library: math.
Imported by:
- biometrics/engine/modalities.py (registers extract_from_image and compare)
- biometrics/config/settings.py documents TARGET_WIDTH and TARGET_HEIGHT
Covered by tests: biometrics/tests/test_fingerprint_features.py,
biometrics/tests/test_multimodal_flow.py,
biometrics/tests/test_sealed_biometrics_flow.py.

Settings / parameters
---------------------
- TARGET_WIDTH = TARGET_HEIGHT = 128 -- Resolution the image is resized to.
- NORMALISE_WINDOW = 17 / NORMALISE_FLOOR = 4.0 -- Local-normalisation window
  and the minimum spread (in gray levels) so that flat regions are not
  amplified into noise.
- SMOOTH_SIGMA = 1.0 -- Gaussian smoothing applied before taking gradients.
- BLOCK_SIZE = 8 -- Block side in pixels; GRID_SIZE = 128 / 8 = 16 cells per
  side.
- FEATURE_VECTOR_LENGTH = GRID_SIZE * GRID_SIZE * 2 = 512
- MIN_CONTRAST = 8 -- Minimum gray-level range an image must span.
- MIN_COHERENCE = 0.25 -- Mean coherence below which a template is treated
  as having no ridge evidence.
- COARSE_ROTATION_STEP / FINE_ROTATION_STEP / FINE_ROTATION_SPAN -- Rotation
  search granularity in degrees (15, 3 and 7.5).
- COARSE_SHIFT = 1 / FINE_SHIFT = 2 -- Shift search range, in cells of the
  coarse and the fine grid respectively.
- COARSE_CANDIDATES = 3 -- Coarse alignments carried into the fine pass.
- MIN_OVERLAP = 0.4 -- Fraction of cells that must overlap after alignment.
- SCORE_POWER = 6.0 -- Exponent mapping raw agreement to the reported similarity;
  chosen so that the default threshold sits at about 1% impostor acceptance on
  the development impressions.

Edge cases
----------
- extract_from_pixels() raises FingerprintFeatureError: "width and height must
  be positive." for non-integer, boolean, zero or negative dimensions, and
  "pixel buffer does not match dimensions." for a wrong-sized buffer.
- extract_from_pixels() raises FingerprintFeatureError: "fingerprint image has
  insufficient ridge contrast." when the image spans fewer than MIN_CONTRAST
  gray levels, and "fingerprint image contains no usable ridge pattern." when
  no region shows coherent ridges (a uniform, noise-only or fully blurred
  capture). Such images cannot be enrolled.
- compare() raises FingerprintFeatureError: "feature vectors must be the same
  length." when the lengths differ, which is how a template created by an
  earlier extractor is detected; the owner must re-enrol. Templates of the
  right length that contain non-finite values, or that have too little ridge
  evidence or overlap, score 0.0.

Known limitations
-----------------
- The template stores the ridge flow field only. It does not detect minutiae
  (ridge endings and bifurcations), so it separates fingers by the overall
  pattern (loops, whorls, arches and where their cores sit) rather than by
  fine ridge detail. Fingers of the same pattern class that have similar
  layouts are harder to tell apart than this implies on well-separated
  examples; minutiae matching would be needed for that.
- Alignment covers rotation of any angle and shifts of up to about two cells
  (16 pixels at the analysis resolution). Very partial prints, strong
  non-linear skin distortion, scars and cuts reduce the score.
- Resizing to a fixed square resolution assumes the sensor's pixel pitch is the
  same at enrolment and verification.
- It does not detect a fake finger or a replayed image.
- SCORE_POWER was calibrated on synthetic development impressions. It must be
  re-checked against impressions from the real scanner before the default
  threshold is relied upon.

Examples
--------
Call shapes only, not a runnable script: width, height, pixels and path stand
for values the caller supplies.

::

    from biometrics.features.fingerprint_features import (
        extract_from_pixels,
        extract_from_image,
        compare,
    )
    template = extract_from_pixels(width, height, pixels)
    probe = extract_from_image(path)
    score = compare(template, probe)
"""
import math

from biometrics.codecs import image_loader, image_tools

TARGET_WIDTH = 128
TARGET_HEIGHT = 128
NORMALISE_WINDOW = 17
NORMALISE_FLOOR = 4.0
SMOOTH_SIGMA = 1.0
BLOCK_SIZE = 8
GRID_SIZE = TARGET_WIDTH // BLOCK_SIZE
# (cos 2t, sin 2t) of the ridge orientation, scaled by coherence, per grid cell
FEATURE_VECTOR_LENGTH = GRID_SIZE * GRID_SIZE * 2
MIN_CONTRAST = 8
MIN_COHERENCE = 0.25
COARSE_ROTATION_STEP = 15.0
FINE_ROTATION_STEP = 3.0
FINE_ROTATION_SPAN = 7.5
COARSE_SHIFT = 1
FINE_SHIFT = 2
COARSE_CANDIDATES = 3
MIN_OVERLAP = 0.4
SCORE_POWER = 6.0


class FingerprintFeatureError(ValueError):
    """Raised when fingerprint feature extraction or comparison cannot proceed."""


# ---------------------------------------------------------------- extraction

def _smooth_kernel(sigma: float) -> list:
    radius = max(1, int(math.ceil(2.5 * sigma)))
    weights = [math.exp(-(i * i) / (2.0 * sigma * sigma)) for i in range(-radius, radius + 1)]
    total = sum(weights)
    return [w / total for w in weights]


_SMOOTH = _smooth_kernel(SMOOTH_SIGMA)


def _smooth_line(line: list) -> list:
    radius = len(_SMOOTH) // 2
    size = len(line)
    padded = ([line[min(size - 1, radius - i)] for i in range(radius)] + line +
              [line[max(0, size - 2 - i)] for i in range(radius)])
    out = [0.0] * size
    for tap, weight in enumerate(_SMOOTH):
        out = [o + weight * v for o, v in zip(out, padded[tap:tap + size])]
    return out


def _local_normalise(rows: list) -> list:
    """(pixel - local mean) / (local spread + floor), via summed-area tables."""
    height, width = len(rows), len(rows[0])
    sums = [[0.0] * (width + 1) for _ in range(height + 1)]
    squares = [[0.0] * (width + 1) for _ in range(height + 1)]
    for r in range(height):
        run = run_sq = 0.0
        row = rows[r]
        for c in range(width):
            run += row[c]
            run_sq += row[c] * row[c]
            sums[r + 1][c + 1] = sums[r][c + 1] + run
            squares[r + 1][c + 1] = squares[r][c + 1] + run_sq
    half = NORMALISE_WINDOW // 2
    out = []
    for r in range(height):
        r0, r1 = max(0, r - half), min(height, r + half + 1)
        out_row = []
        for c in range(width):
            c0, c1 = max(0, c - half), min(width, c + half + 1)
            area = (r1 - r0) * (c1 - c0)
            total = sums[r1][c1] - sums[r0][c1] - sums[r1][c0] + sums[r0][c0]
            total_sq = squares[r1][c1] - squares[r0][c1] - squares[r1][c0] + squares[r0][c0]
            mean = total / area
            spread = math.sqrt(max(total_sq / area - mean * mean, 0.0))
            out_row.append((rows[r][c] - mean) / (spread + NORMALISE_FLOOR))
        out.append(out_row)
    return out


def extract_from_pixels(width: int, height: int, pixels: bytes) -> list:
    """Extract the fixed-length ridge-flow template from a grayscale image."""
    if (isinstance(width, bool) or isinstance(height, bool)
            or not isinstance(width, int) or not isinstance(height, int)
            or width <= 0 or height <= 0):
        raise FingerprintFeatureError("width and height must be positive.")
    if len(pixels) != width * height:
        raise FingerprintFeatureError("pixel buffer does not match dimensions.")
    resized = image_tools.resize_nearest(width, height, pixels, TARGET_WIDTH, TARGET_HEIGHT)
    if max(resized) - min(resized) < MIN_CONTRAST:
        raise FingerprintFeatureError("fingerprint image has insufficient ridge contrast.")
    rows = [[float(v) for v in resized[r * TARGET_WIDTH:(r + 1) * TARGET_WIDTH]]
            for r in range(TARGET_HEIGHT)]
    rows = _local_normalise(rows)
    horizontal = [_smooth_line(row) for row in rows]
    columns = [_smooth_line(list(col)) for col in zip(*horizontal)]
    image = [list(row) for row in zip(*columns)]

    # Central-difference gradients, replicated at the borders.
    gx = [[(row[min(c + 1, TARGET_WIDTH - 1)] - row[max(c - 1, 0)]) * 0.5
           for c in range(TARGET_WIDTH)] for row in image]
    gy = [[(image[min(r + 1, TARGET_HEIGHT - 1)][c] - image[max(r - 1, 0)][c]) * 0.5
           for c in range(TARGET_WIDTH)] for r in range(TARGET_HEIGHT)]

    tensor = []
    for block_row in range(GRID_SIZE):
        line = []
        for block_col in range(GRID_SIZE):
            sxx = syy = sxy = 0.0
            for r in range(block_row * BLOCK_SIZE, (block_row + 1) * BLOCK_SIZE):
                row_x, row_y = gx[r], gy[r]
                for c in range(block_col * BLOCK_SIZE, (block_col + 1) * BLOCK_SIZE):
                    dx, dy = row_x[c], row_y[c]
                    sxx += dx * dx
                    syy += dy * dy
                    sxy += dx * dy
            line.append((sxx, syy, sxy))
        tensor.append(line)

    template = []
    floor = 1e-6 * BLOCK_SIZE * BLOCK_SIZE
    coherence_total = 0.0
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            sxx = syy = sxy = 0.0
            for rr in range(max(0, r - 1), min(GRID_SIZE, r + 2)):
                for cc in range(max(0, c - 1), min(GRID_SIZE, c + 2)):
                    a, b, d = tensor[rr][cc]
                    sxx += a
                    syy += b
                    sxy += d
            total = sxx + syy + floor
            cos2, sin2 = (sxx - syy) / total, 2.0 * sxy / total
            template.extend((cos2, sin2))
            coherence_total += math.hypot(cos2, sin2)
    if coherence_total / (GRID_SIZE * GRID_SIZE) < MIN_COHERENCE:
        raise FingerprintFeatureError("fingerprint image contains no usable ridge pattern.")
    return template


def extract_from_image(path) -> list:
    """Load an image file and extract its fingerprint feature vector."""
    loaded = image_loader.load_image(path)
    return extract_from_pixels(loaded["width"], loaded["height"], loaded["pixels"])


# ------------------------------------------------------------------ matching

def _rotated(cos2: list, sin2: list, size: int, degrees: float) -> tuple:
    """Rotate a flow field about its centre by ``degrees``; zero-filled outside."""
    phi = math.radians(degrees)
    co, si = math.cos(phi), math.sin(phi)
    c2, s2 = math.cos(2 * phi), math.sin(2 * phi)
    centre = (size - 1) / 2.0
    out_c, out_s = [0.0] * (size * size), [0.0] * (size * size)
    last = size - 1
    for r in range(size):
        y = r - centre
        for c in range(size):
            x = c - centre
            sx, sy = co * x + si * y + centre, -si * x + co * y + centre
            if sx < 0 or sy < 0 or sx > last or sy > last:
                continue
            x0, y0 = int(sx), int(sy)
            x1, y1 = min(x0 + 1, last), min(y0 + 1, last)
            fx, fy = sx - x0, sy - y0
            w00, w10, w01, w11 = (1 - fx) * (1 - fy), fx * (1 - fy), (1 - fx) * fy, fx * fy
            i00, i10, i01, i11 = y0 * size + x0, y0 * size + x1, y1 * size + x0, y1 * size + x1
            vc = w00 * cos2[i00] + w10 * cos2[i10] + w01 * cos2[i01] + w11 * cos2[i11]
            vs = w00 * sin2[i00] + w10 * sin2[i10] + w01 * sin2[i01] + w11 * sin2[i11]
            out_c[r * size + c] = c2 * vc - s2 * vs
            out_s[r * size + c] = s2 * vc + c2 * vs
    return out_c, out_s


def _pooled(cos2: list, sin2: list, size: int) -> tuple:
    """Average 2 x 2 groups of cells into a field of half the side."""
    half = size // 2
    out_c, out_s = [0.0] * (half * half), [0.0] * (half * half)
    for r in range(half):
        for c in range(half):
            idx = [(2 * r) * size + 2 * c, (2 * r) * size + 2 * c + 1,
                   (2 * r + 1) * size + 2 * c, (2 * r + 1) * size + 2 * c + 1]
            out_c[r * half + c] = sum(cos2[i] for i in idx) / 4.0
            out_s[r * half + c] = sum(sin2[i] for i in idx) / 4.0
    return out_c, out_s


def _best_shift(a: tuple, b: tuple, size: int, shift: int) -> tuple:
    """Best (agreement, dx, dy) over integer shifts of ``b`` against ``a``."""
    a_c, a_s = a
    b_c, b_s = b
    a_mag = [math.hypot(x, y) for x, y in zip(a_c, a_s)]
    b_mag = [math.hypot(x, y) for x, y in zip(b_c, b_s)]
    best = (-1.0, 0, 0)
    minimum = MIN_OVERLAP * size * size
    for dy in range(-shift, shift + 1):
        for dx in range(-shift, shift + 1):
            dot = norm = 0.0
            cells = 0
            x_lo, x_hi = max(0, dx), min(size, size + dx)
            for r in range(max(0, dy), min(size, size + dy)):
                ia = r * size
                ib = (r - dy) * size - dx
                for c in range(x_lo, x_hi):
                    ma, mb = a_mag[ia + c], b_mag[ib + c]
                    if ma > 0.0 and mb > 0.0:
                        dot += a_c[ia + c] * b_c[ib + c] + a_s[ia + c] * b_s[ib + c]
                        norm += ma * mb
                        cells += 1
            if cells >= minimum and norm > 0.0:
                value = dot / norm
                if value > best[0]:
                    best = (value, dx, dy)
    return best


def compare(vector_a: list, vector_b: list) -> float:
    """Similarity in [0.0, 1.0] between two fingerprint templates.

    The probe's flow field is rotated and shifted to best align with the
    enrolled one, and the coherence-weighted agreement of ridge directions in
    the overlap, raised to SCORE_POWER, is returned. Identical templates score
    exactly 1.0; malformed or non-finite templates, and templates with no
    ridge evidence or no overlap, score 0.0.
    """
    if len(vector_a) != len(vector_b):
        raise FingerprintFeatureError("feature vectors must be the same length.")
    if len(vector_a) != FEATURE_VECTOR_LENGTH:
        return 0.0
    try:
        a = [float(v) for v in vector_a]
        b = [float(v) for v in vector_b]
    except (TypeError, ValueError, OverflowError):
        return 0.0
    if not all(math.isfinite(v) for v in a + b):
        return 0.0
    cells = GRID_SIZE * GRID_SIZE
    a_c, a_s, b_c, b_s = a[0::2], a[1::2], b[0::2], b[1::2]
    if (sum(math.hypot(x, y) for x, y in zip(a_c, a_s)) / cells < MIN_COHERENCE or
            sum(math.hypot(x, y) for x, y in zip(b_c, b_s)) / cells < MIN_COHERENCE):
        return 0.0

    coarse_size = GRID_SIZE // 2
    pooled_a = _pooled(a_c, a_s, GRID_SIZE)
    pooled_b = _pooled(b_c, b_s, GRID_SIZE)
    candidates = []
    steps = int(round(360.0 / COARSE_ROTATION_STEP))
    for step in range(steps):
        degrees = step * COARSE_ROTATION_STEP
        rotated = _rotated(pooled_b[0], pooled_b[1], coarse_size, degrees)
        value, dx, dy = _best_shift(pooled_a, rotated, coarse_size, COARSE_SHIFT)
        candidates.append((value, degrees, dx, dy))
    candidates.sort(reverse=True)

    best = -1.0
    offsets = int(round(FINE_ROTATION_SPAN / FINE_ROTATION_STEP))
    for _, degrees, dx, dy in candidates[:COARSE_CANDIDATES]:
        for k in range(-offsets, offsets + 1):
            fine_degrees = degrees + k * FINE_ROTATION_STEP
            rotated = _rotated(b_c, b_s, GRID_SIZE, fine_degrees)
            value, _, _ = _best_shift((a_c, a_s), rotated, GRID_SIZE, FINE_SHIFT)
            if value > best:
                best = value
    if best <= 0.0:
        return 0.0
    return min(1.0, best) ** SCORE_POWER
