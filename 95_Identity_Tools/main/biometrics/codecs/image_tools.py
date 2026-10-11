"""
File: biometrics/codecs/image_tools.py

Purpose
-------
Pure-Python grayscale image manipulation used to prepare template inputs.

Public interface:
- class ImageToolsError(ValueError) -- Raised on invalid dimensions or
  malformed pixel buffers.
- crop_center(width, height, pixels, target_width, target_height) -- Crop the
  centered ``target_width x target_height`` region.
- resize_nearest(width, height, pixels, target_width, target_height) -- Resize
  via nearest-neighbor sampling.
- normalize(pixels) -- Stretch pixel values to fill the full 0-255 range.
- block_grid_means(width, height, pixels, grid_size) -- Reduce an image to a
  ``grid_size x grid_size`` grid of block-mean values.
- sobel_gradient_magnitude(width, height, pixels) -- Approximate edge strength
  at every pixel using a 3x3 Sobel operator.

Design notes:

Every biometric template in this project is ultimately a fixed-size grid of
values derived from a variable-size input (a captured image, a decoded video
frame). These functions do the two things every feature extractor needs before
it can compute anything: get the image to a known size, and reduce it to a
``grid_size x grid_size`` block-mean summary. No third-party imaging library is
used; everything here is nested-loop arithmetic over flat ``bytes``.

Communication / relationships
-----------------------------
Standard library: none.
Imported by:
- biometrics/features/fingerprint_features.py
- biometrics/features/liveness.py
- biometrics/features/video_features.py
Covered by tests: biometrics/tests/test_codec_and_dsp_support.py.

Settings / parameters
---------------------
- MIN_DIMENSION = 1
- MAX_DIMENSION = 8192

Edge cases
----------
- _check_image() raises ImageToolsError: "width and height must be at least 1."
- _check_image() raises ImageToolsError: "width or height exceeds the supported
  maximum."
- _check_image() raises ImageToolsError: "expected {...} pixel bytes, got
  {...}."
- _check_target() raises ImageToolsError: "target dimensions must be at least
  1."
- _check_target() raises ImageToolsError: "target width or height exceeds the
  supported maximum."
- block_grid_means() raises ImageToolsError: "grid_size must be at least 1."
- block_grid_means() raises ImageToolsError: "grid_size cannot exceed the
  image's width or height."

Known limitations
-----------------
- 8-bit grayscale only. A pixel buffer is a flat, row-major bytes object whose
  length must equal width x height; there is no color, no row padding, and no
  support for other bit depths.
- resize_nearest() does no filtering, so shrinking a detailed image aliases.
  That is deliberate (it never invents a pixel value and is reproducible across
  platforms) but it means fine texture can change the template when the source
  resolution changes.
- crop_center() pads a source smaller than the target with black (0) pixels,
  centered, so a padded border can influence the features built from it.
- normalize() stretches against the whole buffer's minimum and maximum, so one
  outlier pixel sets the range for the entire image. A flat image is returned
  unchanged.
- sobel_gradient_magnitude() is a per-pixel Python loop with a closure call for
  every neighbor read. It took about a second for 256 x 256 in a test run, and
  MAX_DIMENSION (8192) allows images about a thousand times larger, so a
  maximum-size image would take many minutes. Magnitudes are returned as
  unscaled floats, not clamped to 0-255.

Examples
--------
Run from the repository root.

::

    from biometrics.codecs.image_tools import (
        block_grid_means,
        crop_center,
        normalize,
        resize_nearest,
        sobel_gradient_magnitude,
    )

    # A 16 x 16 grayscale gradient: flat, row-major bytes, width * height long.
    width, height = 16, 16
    pixels = bytes((x * 8 + y * 4) % 256
                   for y in range(height) for x in range(width))

    small = resize_nearest(width, height, pixels, 8, 8)
    crop_width, crop_height, cropped = crop_center(8, 8, small, 4, 4)
    stretched = normalize(cropped)

    print(block_grid_means(width, height, pixels, 4))    # 16 block means
    print(max(sobel_gradient_magnitude(8, 8, small)))    # strongest edge
"""

MIN_DIMENSION = 1
MAX_DIMENSION = 8192


class ImageToolsError(ValueError):
    """Raised on invalid dimensions or malformed pixel buffers."""


def _check_image(width: int, height: int, pixels: bytes) -> None:
    if width < MIN_DIMENSION or height < MIN_DIMENSION:
        raise ImageToolsError("width and height must be at least 1.")
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise ImageToolsError("width or height exceeds the supported maximum.")
    if len(pixels) != width * height:
        raise ImageToolsError(
            f"expected {width * height} pixel bytes, got {len(pixels)}."
        )


def _check_target(target_width: int, target_height: int) -> None:
    """Validate a requested output size for a resize/crop.

    Fix 2 (2026-09-11): bound target dimensions against MAX_DIMENSION, not
    just >= 1. _check_image() already refuses a SOURCE image larger than
    MAX_DIMENSION, but resize_nearest()/crop_center() previously validated
    only that their TARGET dimensions were >= 1 -- so an out-of-range target
    would allocate target_width * target_height bytes with no ceiling. Not
    reachable from today's fixed-constant callers (fingerprint/template paths
    pass 64/128), but a shared image utility should refuse an out-of-range
    target exactly as it refuses an out-of-range source.
    """
    if target_width < MIN_DIMENSION or target_height < MIN_DIMENSION:
        raise ImageToolsError("target dimensions must be at least 1.")
    if target_width > MAX_DIMENSION or target_height > MAX_DIMENSION:
        raise ImageToolsError("target width or height exceeds the supported maximum.")


def crop_center(width: int, height: int, pixels: bytes, target_width: int, target_height: int) -> tuple:
    """Crop the centered ``target_width x target_height`` region.

    If the source is smaller than the target in either dimension, the image is
    first padded with black (0) pixels so the crop never reads out of bounds.
    """
    _check_image(width, height, pixels)
    _check_target(target_width, target_height)
    pad_width = max(width, target_width)
    pad_height = max(height, target_height)
    if pad_width != width or pad_height != height:
        width, height, pixels = _pad_to(width, height, pixels, pad_width, pad_height)
    left = (width - target_width) // 2
    top = (height - target_height) // 2
    out = bytearray(target_width * target_height)
    for row in range(target_height):
        source_start = (top + row) * width + left
        out[row * target_width:(row + 1) * target_width] = pixels[
            source_start:source_start + target_width
        ]
    return target_width, target_height, bytes(out)


def _pad_to(width: int, height: int, pixels: bytes, new_width: int, new_height: int) -> tuple:
    left = (new_width - width) // 2
    top = (new_height - height) // 2
    out = bytearray(new_width * new_height)
    for row in range(height):
        destination_start = (top + row) * new_width + left
        out[destination_start:destination_start + width] = pixels[
            row * width:(row + 1) * width
        ]
    return new_width, new_height, bytes(out)


def resize_nearest(width: int, height: int, pixels: bytes, target_width: int, target_height: int) -> bytes:
    """Resize via nearest-neighbor sampling.

    Nearest neighbor is chosen over interpolation deliberately: it never
    invents a pixel value that was not present in the source, which keeps
    template generation reproducible without floating-point rounding
    differences across platforms.
    """
    _check_image(width, height, pixels)
    _check_target(target_width, target_height)
    out = bytearray(target_width * target_height)
    for target_row in range(target_height):
        source_row = min(height - 1, (target_row * height) // target_height)
        row_offset = source_row * width
        out_offset = target_row * target_width
        for target_col in range(target_width):
            source_col = min(width - 1, (target_col * width) // target_width)
            out[out_offset + target_col] = pixels[row_offset + source_col]
    return bytes(out)


def normalize(pixels: bytes) -> bytes:
    """Stretch pixel values to fill the full 0-255 range.

    A flat (constant) input is returned unchanged rather than divided by a
    zero range, since there is no meaningful contrast to stretch.
    """
    if not pixels:
        return pixels
    low = min(pixels)
    high = max(pixels)
    if high == low:
        return bytes(pixels)
    scale = 255.0 / (high - low)
    return bytes(int(round((value - low) * scale)) for value in pixels)


def block_grid_means(width: int, height: int, pixels: bytes, grid_size: int) -> list:
    """Reduce an image to a ``grid_size x grid_size`` grid of block-mean values.

    This is the core dimensionality reduction behind every image-derived
    template in this project: it turns a variable-resolution capture into a
    fixed, small, comparable summary. Rows and columns are divided as evenly
    as integer arithmetic allows so every block width differs from its
    neighbors by at most one pixel.
    """
    _check_image(width, height, pixels)
    if grid_size < 1:
        raise ImageToolsError("grid_size must be at least 1.")
    # Fix 1 (2026-09-09): reject a grid_size larger than the image in either
    # dimension. Previously such a grid produced zero-width/zero-height blocks
    # whose `count` was 0, and the `total / count if count else 0.0` guard
    # silently substituted 0.0 -- yielding a feature vector that looked valid
    # but was meaningless. A misconfigured extractor now fails loudly instead
    # of producing a degenerate template.
    if grid_size > width or grid_size > height:
        raise ImageToolsError(
            "grid_size cannot exceed the image's width or height."
        )
    row_bounds = _partition(height, grid_size)
    col_bounds = _partition(width, grid_size)
    means = []
    for row_start, row_end in row_bounds:
        for col_start, col_end in col_bounds:
            total = 0
            count = 0
            for row in range(row_start, row_end):
                offset = row * width
                total += sum(pixels[offset + col_start:offset + col_end])
                count += col_end - col_start
            means.append(total / count if count else 0.0)
    return means


def _partition(total: int, parts: int) -> list:
    base, remainder = divmod(total, parts)
    bounds = []
    cursor = 0
    for index in range(parts):
        size = base + (1 if index < remainder else 0)
        bounds.append((cursor, cursor + size))
        cursor += size
    return bounds


def sobel_gradient_magnitude(width: int, height: int, pixels: bytes) -> list:
    """Approximate edge strength at every pixel using a 3x3 Sobel operator.

    Used by the fingerprint feature extractor to build a ridge-orientation
    summary. Border pixels use replicated edge padding rather than being
    skipped, so the output has the same dimensions as the input.
    """
    _check_image(width, height, pixels)

    def at(row: int, col: int) -> int:
        row = min(max(row, 0), height - 1)
        col = min(max(col, 0), width - 1)
        return pixels[row * width + col]

    magnitudes = [0.0] * (width * height)
    for row in range(height):
        for col in range(width):
            gx = (
                at(row - 1, col + 1) + 2 * at(row, col + 1) + at(row + 1, col + 1)
                - at(row - 1, col - 1) - 2 * at(row, col - 1) - at(row + 1, col - 1)
            )
            gy = (
                at(row + 1, col - 1) + 2 * at(row + 1, col) + at(row + 1, col + 1)
                - at(row - 1, col - 1) - 2 * at(row - 1, col) - at(row - 1, col + 1)
            )
            magnitudes[row * width + col] = (gx * gx + gy * gy) ** 0.5
    return magnitudes




