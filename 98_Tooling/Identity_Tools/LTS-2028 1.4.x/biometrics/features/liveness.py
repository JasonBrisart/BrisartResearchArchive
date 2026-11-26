"""
File: biometrics/features/liveness.py

Purpose
-------
Motion-presence gate for the video modality. It measures how much a decoded
BRVID clip changes from frame to frame, separates change in the picture from
change that is only sensor noise or a flicker in overall brightness, and
reports whether real motion is present, so a still photograph, a clip built
from one repeated frame, or a static scene under a flickering light can be
refused at enrollment and verification.

Public interface:
- class LivenessError(ValueError) -- Raised when liveness cannot be assessed
  due to malformed input.
- compute_motion_energy(width, height, frames) -- Mean absolute per-pixel
  frame-to-frame difference across a clip.
- compute_coherent_motion(width, height, frames) -- Fraction of image blocks
  that show localised change standing clearly above the clip's own noise level
  (or None when the frames are too small to analyse).
- assess_liveness(width, height, frames, threshold=DEFAULT_LIVENESS_THRESHOLD)
  -- Assess whether a decoded BRVID frame sequence shows real motion.

Design notes:

What it detects. The raw frame-to-frame pixel difference cannot tell a moving
scene from a still one: every camera adds sensor noise, so a photograph held
in front of the lens changes from frame to frame too, and so does anything
under a mains-powered light whose brightness ripples. Two measurements are
therefore combined.

1. compute_motion_energy() is the mean absolute pixel difference between
   consecutive frames. It is the original measure and it must reach
   ``threshold``; a perfectly static clip fails here.
2. compute_coherent_motion() reduces every frame to a 16 x 16 grid of block
   means, which averages independent pixel noise down by the block area. The
   sensor noise level is estimated from the frames themselves, from their
   finest-scale texture (the Immerkaer estimator), so it does not depend on how
   much of the picture is moving. For each pair of consecutive frames the
   overall brightness change is removed (an offset and a gain fitted by least
   squares, which is what a flickering light or an auto-exposure step
   produces), and the blocks whose residual exceeds five times the expected
   noise of a block difference, and that have a neighbouring block doing the
   same, are counted. Noise rarely produces such clusters; a moving edge, a
   blinking eye, a moving mouth or a shifting scene does. The clip must show
   at least COHERENT_MOTION_THRESHOLD of such blocks.

A clip is reported live only when both measurements pass.

What it does not detect. This is a motion-presence check, not liveness or
anti-spoofing in the research sense. It does not catch:
- a replayed recording of the enrolled person, which has real motion;
- a high-quality 3D mask or deepfake with natural micro-motion;
- a printed photo or a screen physically moved in front of the camera with
  enough movement to change the picture.

It also refuses a live subject who is completely still for the whole clip and
does not blink or speak, because nothing in the picture changes. A clip long
enough to contain a blink avoids this.

The same limit is stated in biometrics/README.md ("Video features and motion
checks") and in docs/BSR2_INTEGRATION.md ("Biometrics protection and
disclosure").

Communication / relationships
-----------------------------
Depends on (project modules):
- biometrics.codecs.image_tools (block-mean reduction)
Standard library: math.
Imported by:
- biometrics/engine/enrollment.py
- biometrics/engine/verification.py
Covered by tests: biometrics/tests/test_liveness.py.

Settings / parameters
---------------------
- DEFAULT_LIVENESS_THRESHOLD = 0.75 -- Minimum mean absolute frame difference.
- MIN_FRAMES_FOR_LIVENESS = 2
- COHERENT_GRID = 16 -- Side of the block grid each frame is reduced to
  (smaller frames use their own side; below COHERENT_MIN_GRID the coherent
  test is skipped).
- COHERENT_EXCEED_SIGMAS = 5.0 -- A block counts as moving when its residual is
  more than this many noise levels.
- COHERENT_NOISE_FLOOR = 0.35 -- Smallest block-difference noise level used, in
  gray levels, so a noise-free clip does not make rounding error look like
  motion.
- COHERENT_NOISE_FRAMES = 4 -- Number of leading frames used to estimate the
  sensor noise.
- COHERENT_MOTION_THRESHOLD = 0.005 -- Required fraction of moving blocks
  (0.5%), averaged over all frame pairs.

Edge cases
----------
- _mean_absolute_frame_difference() raises LivenessError: "frame byte length
  does not match {...}x{...} dimensions."
- compute_motion_energy() raises LivenessError: "width and height must be
  positive." for non-integer, boolean, zero or negative dimensions.
- compute_motion_energy() raises LivenessError: "at least one frame is required
  to assess liveness."
- assess_liveness() raises LivenessError: "threshold must be positive." for a
  zero, negative, non-finite or non-numeric threshold.
- A single frame, or frames smaller than COHERENT_MIN_GRID pixels on a side,
  cannot be analysed for coherent motion: a single frame reports no motion and
  fails, and a too-small clip is judged by the frame-difference gate alone.

Known limitations
-----------------
- Tracked in docs/KNOWN_ISSUES.md: KI-001: Video liveness threshold is
  uncalibrated against real camera hardware.
- COHERENT_MOTION_THRESHOLD was calibrated on synthetic clips. Real subjects,
  lenses and lighting will need it re-checked. Compression artefacts and
  rolling-shutter banding can look like moving blocks.
- The least-squares correction removes a uniform change of brightness, not a
  flicker that varies across the picture.

Examples
--------
Call shapes only, not a runnable script: width, height, frames stand for values
the caller supplies.

::

    from biometrics.features.liveness import (
        compute_motion_energy,
        compute_coherent_motion,
        assess_liveness,
    )
    compute_motion_energy(width, height, frames)
    compute_coherent_motion(width, height, frames)
    assess_liveness(width, height, frames)
"""
import math

from biometrics.codecs import image_tools

DEFAULT_LIVENESS_THRESHOLD = 0.75
MIN_FRAMES_FOR_LIVENESS = 2
COHERENT_GRID = 16
COHERENT_MIN_GRID = 4
COHERENT_EXCEED_SIGMAS = 5.0
COHERENT_NOISE_FLOOR = 0.35
COHERENT_NOISE_FRAMES = 4
COHERENT_MOTION_THRESHOLD = 0.005


class LivenessError(ValueError):
    """Raised when liveness cannot be assessed due to malformed input."""


def _check_dimensions(width: int, height: int) -> None:
    if (isinstance(width, bool) or isinstance(height, bool)
            or not isinstance(width, int) or not isinstance(height, int)
            or width <= 0 or height <= 0):
        raise LivenessError("width and height must be positive.")


def _mean_absolute_frame_difference(width: int, height: int, previous: bytes, current: bytes) -> float:
    frame_bytes = width * height
    if len(previous) != frame_bytes or len(current) != frame_bytes:
        raise LivenessError(
            f"frame byte length does not match {width}x{height} dimensions."
        )
    total_difference = sum(abs(a - b) for a, b in zip(previous, current))
    return total_difference / frame_bytes


def compute_motion_energy(width: int, height: int, frames: list) -> float:
    """Mean absolute per-pixel frame-to-frame difference across a clip.

    Returns 0.0 for a clip with fewer than MIN_FRAMES_FOR_LIVENESS frames,
    since there is no consecutive pair to compare -- this is a real zero,
    not a missing-data sentinel, and callers should treat it as "no motion
    detected" rather than special-casing it further.
    """
    _check_dimensions(width, height)
    if not frames:
        raise LivenessError("at least one frame is required to assess liveness.")
    if len(frames) < MIN_FRAMES_FOR_LIVENESS:
        return 0.0
    differences = [
        _mean_absolute_frame_difference(width, height, previous, current)
        for previous, current in zip(frames, frames[1:])
    ]
    return sum(differences) / len(differences)


def _residual(previous: list, current: list) -> list:
    """Block differences with the best-fit offset and gain change removed."""
    count = len(previous)
    mean_x = sum(previous) / count
    differences = [b - a for a, b in zip(previous, current)]
    mean_d = sum(differences) / count
    variance = sum((a - mean_x) ** 2 for a in previous)
    gain = 0.0
    if variance > 0.0:
        gain = sum((a - mean_x) * (d - mean_d)
                   for a, d in zip(previous, differences)) / variance
    offset = mean_d - gain * mean_x
    return [d - offset - gain * a for a, d in zip(previous, differences)]


def _sensor_noise(width: int, height: int, frame: bytes) -> float:
    """Standard deviation of sensor noise from the frame's finest texture.

    Immerkaer's estimator: the mean absolute response of a Laplacian-difference
    mask, which cancels smooth image structure and keeps uncorrelated noise.
    Detail in the picture can only make the estimate larger, never smaller.
    """
    if width < 3 or height < 3:
        return 0.0
    total = 0.0
    for row in range(1, height - 1):
        top = frame[(row - 1) * width:row * width]
        mid = frame[row * width:(row + 1) * width]
        bottom = frame[(row + 1) * width:(row + 2) * width]
        total += sum(abs(top[c - 1] - 2 * top[c] + top[c + 1]
                         - 2 * mid[c - 1] + 4 * mid[c] - 2 * mid[c + 1]
                         + bottom[c - 1] - 2 * bottom[c] + bottom[c + 1])
                     for c in range(1, width - 1))
    return math.sqrt(math.pi / 2.0) / (6.0 * (width - 2) * (height - 2)) * total


def compute_coherent_motion(width: int, height: int, frames: list):
    """Fraction of blocks showing localised change above the clip's noise level.

    Returns None when the frames are too small to analyse or there are fewer
    than MIN_FRAMES_FOR_LIVENESS of them.
    """
    _check_dimensions(width, height)
    if not frames:
        raise LivenessError("at least one frame is required to assess liveness.")
    grid = min(COHERENT_GRID, width, height)
    if grid < COHERENT_MIN_GRID or len(frames) < MIN_FRAMES_FOR_LIVENESS:
        return None
    for frame in frames:
        if len(frame) != width * height:
            raise LivenessError(
                f"frame byte length does not match {width}x{height} dimensions."
            )
    blocks = [image_tools.block_grid_means(width, height, frame, grid) for frame in frames]
    residuals = [_residual(a, b) for a, b in zip(blocks, blocks[1:])]
    noise = sorted(_sensor_noise(width, height, frame)
                   for frame in frames[:COHERENT_NOISE_FRAMES])
    sensor = noise[len(noise) // 2]
    block_pixels = (width * height) / float(grid * grid)
    expected = sensor * math.sqrt(2.0 / block_pixels)
    limit = COHERENT_EXCEED_SIGMAS * max(expected, COHERENT_NOISE_FLOOR)
    moving = 0
    for pair in residuals:
        flags = [abs(v) > limit for v in pair]
        for row in range(grid):
            for col in range(grid):
                if not flags[row * grid + col]:
                    continue
                if ((col > 0 and flags[row * grid + col - 1]) or
                        (col < grid - 1 and flags[row * grid + col + 1]) or
                        (row > 0 and flags[(row - 1) * grid + col]) or
                        (row < grid - 1 and flags[(row + 1) * grid + col])):
                    moving += 1
    return moving / (len(residuals) * grid * grid)


def assess_liveness(
    width: int,
    height: int,
    frames: list,
    threshold: float = DEFAULT_LIVENESS_THRESHOLD,
) -> dict:
    """Assess whether a decoded BRVID frame sequence shows real motion.

    Returns {"motion_energy", "threshold", "coherent_motion",
    "coherent_threshold", "is_live"}. `is_live` is the single field every
    caller should actually branch on; the other fields are included so a
    verification/enrollment report can record the actual measured values
    rather than just a pass/fail bit, matching this project's existing
    convention of recording scores alongside thresholds (see
    biometrics.reports.report_writer's per-modality result shape).
    `coherent_motion` is None when the clip is too small to analyse, in which
    case the frame-difference gate decides alone.
    """
    if (isinstance(threshold, bool) or not isinstance(threshold, (int, float))
            or not math.isfinite(threshold) or threshold <= 0):
        raise LivenessError("threshold must be positive.")
    motion_energy = compute_motion_energy(width, height, frames)
    coherent = compute_coherent_motion(width, height, frames)
    passed = motion_energy >= threshold
    if coherent is not None:
        passed = passed and coherent >= COHERENT_MOTION_THRESHOLD
    return {
        "motion_energy": motion_energy,
        "threshold": threshold,
        "coherent_motion": coherent,
        "coherent_threshold": COHERENT_MOTION_THRESHOLD,
        "is_live": passed,
    }
