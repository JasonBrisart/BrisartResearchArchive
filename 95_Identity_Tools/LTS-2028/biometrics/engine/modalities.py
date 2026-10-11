"""
File: biometrics/engine/modalities.py

Purpose
-------
Per-modality dispatch table: feature extraction, comparison, and thresholds.

Public interface:
- class UnsupportedModalityError(ValueError) -- Raised when a modality name has
  no registered extractor.
- supported_modalities() -- List every modality name with a registered
  extractor, sorted.
- extract_from_path(modality, path) -- Extract a feature vector for
  ``modality`` from a file at ``path``.
- compare(modality, vector_a, vector_b) -- Compare two feature vectors for
  ``modality``, returning a similarity score.
- vector_length(modality) -- Return the fixed feature-vector length for
  ``modality``.
- default_threshold(modality) -- Return the default match-acceptance threshold
  for ``modality``.

Design notes:

``enrollment.py`` and ``verification.py`` both need to answer "given a modality
name, how do I turn raw input into a template, and how do I compare two
templates?" without hardcoding a chain of if/elif branches for each of the
three modalities. This module is the single place that answers that question,
so adding a fourth modality later means adding one entry here, not hunting
through both engine files.

Default match thresholds are deliberately conservative (biased toward rejecting
a genuine match rather than accepting an impostor) since this is a
research/reference implementation, not a tuned production biometric system.

Communication / relationships
-----------------------------
Depends on (project modules):
- biometrics.features.fingerprint_features
  (biometrics/features/fingerprint_features.py)
- biometrics.features.video_features (biometrics/features/video_features.py)
- biometrics.features.voice_features (biometrics/features/voice_features.py)
Standard library: none.
Imported by:
- biometrics/app.py
- biometrics/engine/enrollment.py
- biometrics/engine/verification.py
- gui/widgets/dialogs.py
Covered by tests: no test file imports this module directly.

Settings / parameters
---------------------
- DEFAULT_THRESHOLDS = { "voice": 0.85, "fingerprint": 0.80, "video": 0.75, }
- _MODALITIES = dict of 3 entries

Edge cases
----------
- _entry() raises UnsupportedModalityError: "unsupported modality {...};
  expected one of {...}."

Known limitations
-----------------
- No test module imports this file directly; it is exercised only through its
  callers' tests, so check changes manually.

Examples
--------
::

    from biometrics.engine.modalities import (
        supported_modalities,
        extract_from_path,
        compare,
    )
    result = supported_modalities()
    extract_from_path(modality, path)
    compare(modality, vector_a, vector_b)
"""

from biometrics.features import fingerprint_features, video_features, voice_features

DEFAULT_THRESHOLDS = {
    "voice": 0.85,
    "fingerprint": 0.80,
    "video": 0.75,
}


class UnsupportedModalityError(ValueError):
    """Raised when a modality name has no registered extractor."""


def _voice_extract(path):
    return voice_features.extract_from_wav(path)


def _fingerprint_extract(path):
    return fingerprint_features.extract_from_image(path)


def _video_extract(path):
    return video_features.extract_from_video(path)


_MODALITIES = {
    "voice": {
        "extract_from_path": _voice_extract,
        "compare": voice_features.compare,
        "vector_length": voice_features.FEATURE_VECTOR_LENGTH,
    },
    "fingerprint": {
        "extract_from_path": _fingerprint_extract,
        "compare": fingerprint_features.compare,
        "vector_length": fingerprint_features.FEATURE_VECTOR_LENGTH,
    },
    "video": {
        "extract_from_path": _video_extract,
        "compare": video_features.compare,
        "vector_length": video_features.FEATURE_VECTOR_LENGTH,
    },
}


def supported_modalities() -> list:
    """List every modality name with a registered extractor, sorted."""
    return sorted(_MODALITIES.keys())


def _entry(modality: str) -> dict:
    entry = _MODALITIES.get(modality)
    if entry is None:
        raise UnsupportedModalityError(
            f"unsupported modality {modality!r}; expected one of "
            f"{supported_modalities()}."
        )
    return entry


def extract_from_path(modality: str, path) -> list:
    """Extract a feature vector for ``modality`` from a file at ``path``."""
    return _entry(modality)["extract_from_path"](path)


def compare(modality: str, vector_a: list, vector_b: list) -> float:
    """Compare two feature vectors for ``modality``, returning a similarity score."""
    return _entry(modality)["compare"](vector_a, vector_b)


def vector_length(modality: str) -> int:
    """Return the fixed feature-vector length for ``modality``."""
    return _entry(modality)["vector_length"]


def default_threshold(modality: str) -> float:
    """Return the default match-acceptance threshold for ``modality``."""
    _entry(modality)  # validates the modality name
    return DEFAULT_THRESHOLDS[modality]




