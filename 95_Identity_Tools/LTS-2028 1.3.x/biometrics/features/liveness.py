"""
File: biometrics/features/liveness.py

Purpose
-------
Motion-presence gate for the video modality. It measures how much a decoded
BRVID clip changes from frame to frame and reports whether that change reaches
a threshold, so a still photograph or a clip built from one repeated frame can
be refused at enrollment and verification.

Public interface:
- class LivenessError(ValueError) -- Raised when liveness cannot be assessed
  due to malformed input.
- compute_motion_energy(width, height, frames) -- Mean absolute per-pixel
  frame-to-frame difference across a clip.
- assess_liveness(width, height, frames, threshold=DEFAULT_LIVENESS_THRESHOLD)
  -- Assess whether a decoded BRVID frame sequence shows real motion.

Design notes:

What it detects. A still photograph, or any perfectly static scene, held in
front of a camera produces near-zero frame-to-frame pixel change, as does a
synthetic clip built from a single repeated frame. A live capture, even of
someone sitting still, has some change from sensor noise, micro-movement, and
lighting flicker. The module measures the mean absolute pixel difference
between consecutive frames, averaged across the whole clip.

What it does not detect. This is a motion-presence check, not liveness or
anti-spoofing in the research sense. It does not catch:
- a replayed recording of the enrolled person, which has real motion;
- a high-quality 3D mask or deepfake with natural micro-motion;
- a photo physically moved in front of the camera to fake motion.

The same limit is stated in biometrics/README.md ("Video features and motion
checks") and in docs/BSR2_INTEGRATION.md ("Biometrics protection and
disclosure").

Communication / relationships
-----------------------------
Depends on (project modules):
- biometrics.codecs.image_tools (biometrics/codecs/image_tools.py)
Standard library: none.
Imported by:
- biometrics/engine/enrollment.py
- biometrics/engine/verification.py
Covered by tests: biometrics/tests/test_liveness.py.

Settings / parameters
---------------------
- DEFAULT_LIVENESS_THRESHOLD = 0.75
- MIN_FRAMES_FOR_LIVENESS = 2

Edge cases
----------
- _mean_absolute_frame_difference() raises LivenessError: "frame byte length
  does not match {...}x{...} dimensions."
- compute_motion_energy() raises LivenessError: "width and height must be
  positive."
- compute_motion_energy() raises LivenessError: "at least one frame is required
  to assess liveness."
- assess_liveness() raises LivenessError: "threshold must be positive."

Known limitations
-----------------
- Tracked in docs/KNOWN_ISSUES.md: KI-001: Video liveness threshold is
  uncalibrated against real camera hardware

Examples
--------
Call shapes only, not a runnable script: width, height, frames stand for values
the caller supplies.

::

    from biometrics.features.liveness import (
        compute_motion_energy,
        assess_liveness,
    )
    compute_motion_energy(width, height, frames)
    assess_liveness(width, height, frames)
"""

from biometrics.codecs import image_tools

DEFAULT_LIVENESS_THRESHOLD = 0.75
MIN_FRAMES_FOR_LIVENESS = 2


class LivenessError(ValueError):
    """Raised when liveness cannot be assessed due to malformed input."""


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
    if width <= 0 or height <= 0:
        raise LivenessError("width and height must be positive.")
    if not frames:
        raise LivenessError("at least one frame is required to assess liveness.")
    if len(frames) < MIN_FRAMES_FOR_LIVENESS:
        return 0.0
    differences = [
        _mean_absolute_frame_difference(width, height, previous, current)
        for previous, current in zip(frames, frames[1:])
    ]
    return sum(differences) / len(differences)


def assess_liveness(
    width: int,
    height: int,
    frames: list,
    threshold: float = DEFAULT_LIVENESS_THRESHOLD,
) -> dict:
    """Assess whether a decoded BRVID frame sequence shows real motion.

    Returns {"motion_energy", "threshold", "is_live"}. `is_live` is the
    single field every caller should actually branch on; `motion_energy`
    and `threshold` are included so a verification/enrollment report can
    record the actual measured value rather than just a pass/fail bit,
    matching this project's existing convention of recording scores
    alongside thresholds (see biometrics.reports.report_writer's
    per-modality result shape).
    """
    if threshold <= 0:
        raise LivenessError("threshold must be positive.")
    motion_energy = compute_motion_energy(width, height, frames)
    return {
        "motion_energy": motion_energy,
        "threshold": threshold,
        "is_live": motion_energy >= threshold,
    }




