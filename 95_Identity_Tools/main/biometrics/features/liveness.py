"""
File: biometrics/features/liveness.py

Purpose
-------
Reintroduces a liveness/anti-spoofing GATE for the video modality, filling the
gap explicitly documented in biometrics/README.md's Status section ("there is
currently no liveness or anti-spoofing check for any modality -- a recording or
synthetic sample that reproduces the feature vector closely enough will
verify") and in docs/BSR2_INTEGRATION.md's Residual Risks item 7. This is NOT a
resurrection of the old 0.6.0-beta LabID_Beta/core/video.py liveness code --
that code parsed real AVI files and no longer exists; this repository's current
video pipeline stores frames in the from-scratch BRVID container
(biometrics/codecs/video.py), which never had liveness logic.

Public interface:
- class LivenessError(ValueError) -- Raised when liveness cannot be assessed
  due to malformed input.
- compute_motion_energy(width, height, frames) -- Mean absolute per-pixel
  frame-to-frame difference across a clip.
- assess_liveness(width, height, frames, threshold=DEFAULT_LIVENESS_THRESHOLD)
  -- Assess whether a decoded BRVID frame sequence shows real motion.

Design notes:

This module is a new implementation built against BRVID's actual frame data.
WHAT IT DETECTS A still photograph (or any perfectly static scene) held in
front of a camera, or a synthetic clip built from a single repeated frame,
produces near-zero frame-to-frame pixel change. A live capture -- even someone
sitting still -- always has some non-zero change from sensor noise,
micro-movement, and lighting flicker. This module measures exactly that: mean
absolute pixel difference between consecutive frames, averaged across the whole
clip. WHAT IT DOES NOT DETECT This is a MOTION-PRESENCE check, not a
liveness/anti-spoofing check in the research sense. It will NOT catch: - A
video replay attack (playing a real recorded video of the enrolled person back
at the camera) -- that has real motion and passes this gate. - A high-quality
3D mask or deepfake with natural micro-motion. - A photo that is itself
physically wobbled/panned in front of the camera to fake motion. This is stated
plainly rather than left implied, matching this project's existing
"Research-grade" framing (biometrics/README.md's Status section): this closes
the specific "one repeated still frame" gap, not the general
liveness/anti-spoofing problem.

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
::

    from biometrics.features.liveness import (
        compute_motion_energy,
        assess_liveness,
    )
    result = compute_motion_energy(width, height, frames)
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




