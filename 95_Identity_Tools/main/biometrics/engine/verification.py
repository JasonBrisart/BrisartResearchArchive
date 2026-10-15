"""
File: biometrics/engine/verification.py

Purpose
-------
Verification: comparing fresh biometric input against a stored template.

Public interface:
- class VerificationError(ValueError) -- Raised when verification cannot
  proceed (missing template, bad input).
- verify_modality(record, modality, probe_path, master_key, threshold=None,
  allow_static=False) -- Verify a probe file against a record's stored template
  for ``modality``.
- verify_identity(record, probe_sources, master_key, thresholds=None,
  require_all=True, allow_static=False) -- Verify several modalities at once,
  e.g. voice and fingerprint together.

Design notes:

The flow is the reverse of enrollment: open the sealed template for the
requested modality (using the same context construction enrollment used, so a
mismatched identity id or modality fails authentication before any comparison
happens), extract a feature vector from the fresh probe input, and score the
two vectors against each other using the modality's comparison function. The
module reports matched by comparing the score to the selected threshold
(``biometrics.engine.modalities.default_threshold`` unless overridden).

For video only, a motion-presence gate runs before similarity comparison. A
static clip with insufficient frame-to-frame change fails this gate and is
reported as a non-match with a populated "liveness" field, before its
similarity score is ever computed against the stored template -- mirroring the
enforced pass/fail gate design from the project's 0.6.0-beta release,
re-implemented here against the current BRVID-based video pipeline. Pass
allow_static=True (wired to the CLI's --allow-static flag) to skip this gate
entirely, for example to inspect a raw similarity score during debugging.

Communication / relationships
-----------------------------
Depends on (project modules):
- biometrics.codecs.video (biometrics/codecs/video.py)
- biometrics.engine.modalities (biometrics/engine/modalities.py)
- biometrics.features.liveness (biometrics/features/liveness.py)
- biometrics.identity.identity_record (biometrics/identity/identity_record.py)
- crypto.context (crypto/context.py)
- crypto.envelope (crypto/envelope.py)
- crypto.errors (crypto/errors.py)
Standard library: none.
Imported by:
- biometrics/app.py
- gui/tabs/tab_biometrics.py
Covered by tests: biometrics/tests/test_liveness.py,
biometrics/tests/test_multimodal_flow.py,
biometrics/tests/test_sealed_biometrics_flow.py.

Settings / parameters
---------------------
No module-level constants. Tunable defaults are exposed as
keyword arguments:
- verify_modality(threshold=None)
- verify_modality(allow_static=False)
- verify_identity(thresholds=None)
- verify_identity(require_all=True)
- verify_identity(allow_static=False)

Edge cases
----------
- _check_video_liveness() raises VerificationError: "failed to read video probe
  for liveness check: {...}"
- _check_video_liveness() raises VerificationError: "liveness assessment
  failed: {...}"
- verify_modality() raises VerificationError: "identity {...} has no enrolled
  {...} template."
- verify_modality() raises VerificationError: "stored {...} template for {...}
  failed to authenticate: {...}"
- verify_modality() raises VerificationError: "stored template payload does not
  match the requested modality {...}."
- verify_modality() raises VerificationError: "stored template payload has no
  feature vector."
- verify_modality() raises VerificationError: "failed to extract {...} features
  from {...}: {...}"
- verify_identity() raises VerificationError: "at least one probe source is
  required."
- _check_video_liveness(): translates LivenessError into VerificationError; other exceptions may still propagate.
- _check_video_liveness(): translates video_codec.VideoFormatError into
  VerificationError; other exceptions may still propagate.
- verify_modality(): translates (OSError, ValueError) into VerificationError; other exceptions may still propagate.
- verify_modality(): translates Bsr2IntegrationError into VerificationError; other exceptions may still propagate.

Known limitations
-----------------
- LIVENESS GATE (video modality only): before a video probe's similarity score
  is trusted, its raw decoded frames are checked for frame-to-frame pixel changes
  via biometrics.features.liveness.assess_liveness().
- Motion presence is not proof of genuine liveness: this gate does not
  establish that a moving probe is a live person rather than a replay.
- Tracked in docs/KNOWN_ISSUES.md: KI-001: Video liveness threshold is
  uncalibrated against real camera hardware
- Security rests on BSR2, a custom research construction that has not been
  independently audited (see docs/SECURITY.md); do not treat it as a
  replacement for vetted, audited cryptography.

Examples
--------
API usage with an enrolled record, probe paths, and an unlocked master key
supplied by the caller.

Call shapes only, not a runnable script: record, modality, probe_path,
master_key, probe_sources stand for values the caller supplies.

::

    from biometrics.engine.verification import verify_modality, verify_identity
    verify_modality(record, modality, probe_path, master_key)
    verify_identity(record, probe_sources, master_key)
"""

from biometrics.codecs import video as video_codec
from biometrics.engine import modalities
from biometrics.features.liveness import LivenessError, assess_liveness
from biometrics.identity.identity_record import has_modality
from crypto.context import template_context
from crypto.envelope import open_json
from crypto.errors import Bsr2IntegrationError


class VerificationError(ValueError):
    """Raised when verification cannot proceed (missing template, bad input)."""


def _check_video_liveness(probe_path, allow_static: bool) -> dict:
    """Decode a video probe and assess liveness. Returns the liveness dict,
    or None if allow_static=True (gate skipped entirely -- no decode is even
    attempted, so a malformed file that would otherwise fail liveness
    decoding does not block a caller who has explicitly opted out of the
    gate)."""
    if allow_static:
        return None
    try:
        decoded = video_codec.read_video(probe_path)
    except video_codec.VideoFormatError as exc:
        raise VerificationError(f"failed to read video probe for liveness check: {exc}") from exc
    try:
        return assess_liveness(decoded["width"], decoded["height"], decoded["frames"])
    except LivenessError as exc:
        raise VerificationError(f"liveness assessment failed: {exc}") from exc


def verify_modality(
    record: dict,
    modality: str,
    probe_path,
    master_key: bytes,
    threshold: float = None,
    allow_static: bool = False,
) -> dict:
    """Verify a probe file against a record's stored template for ``modality``.

    Returns ``{"modality", "score", "threshold", "matched"}``, plus a
    ``"liveness"`` key when the video modality's gate was actually evaluated
    (omitted for every other modality, and omitted for video when
    allow_static=True). Raises :class:`VerificationError` if the record has
    no template for this modality, or if the stored template fails to open
    (wrong master key, or the template was sealed under a different identity
    id / modality than claimed).
    """
    if not has_modality(record, modality):
        raise VerificationError(
            f"identity {record['identity_id']!r} has no enrolled {modality} template."
        )
    if threshold is None:
        threshold = modalities.default_threshold(modality)

    liveness_result = None
    if modality == "video":
        liveness_result = _check_video_liveness(probe_path, allow_static)
        if liveness_result is not None and not liveness_result["is_live"]:
            return {
                "modality": modality,
                "score": 0.0,
                "threshold": threshold,
                "matched": False,
                "liveness": liveness_result,
            }

    context = template_context(record["identity_id"], modality)
    envelope = record["templates"][modality]
    try:
        payload = open_json(master_key, envelope, context)
    except Bsr2IntegrationError as exc:
        raise VerificationError(
            f"stored {modality} template for {record['identity_id']!r} failed "
            f"to authenticate: {exc}"
        ) from exc
    if payload.get("modality") != modality:
        raise VerificationError(
            f"stored template payload does not match the requested modality "
            f"{modality!r}."
        )
    stored_vector = payload.get("vector")
    if not isinstance(stored_vector, list):
        raise VerificationError("stored template payload has no feature vector.")
    try:
        probe_vector = modalities.extract_from_path(modality, probe_path)
    except (OSError, ValueError) as exc:
        raise VerificationError(
            f"failed to extract {modality} features from {probe_path!r}: {exc}"
        ) from exc
    score = modalities.compare(modality, stored_vector, probe_vector)
    result = {
        "modality": modality,
        "score": score,
        "threshold": threshold,
        "matched": score >= threshold,
    }
    if liveness_result is not None:
        result["liveness"] = liveness_result
    return result


def verify_identity(
    record: dict,
    probe_sources: dict,
    master_key: bytes,
    thresholds: dict = None,
    require_all: bool = True,
    allow_static: bool = False,
) -> dict:
    """Verify several modalities at once, e.g. voice and fingerprint together.

    ``probe_sources`` maps modality name to a probe file path. ``thresholds``
    optionally overrides the per-modality default. ``require_all`` controls
    whether *every* requested modality must match (``True``, the default and
    the more conservative choice for a multimodal check) or whether *any one*
    matching is sufficient (``False``). ``allow_static`` bypasses the video
    liveness gate for every video probe in this call, e.g. for debugging.

    Returns ``{"identity_id", "results", "matched"}`` where ``results`` is a
    list of the same per-modality dicts :func:`verify_modality` returns.
    """
    if not probe_sources:
        raise VerificationError("at least one probe source is required.")
    thresholds = thresholds or {}
    results = []
    for modality, probe_path in probe_sources.items():
        results.append(
            verify_modality(
                record,
                modality,
                probe_path,
                master_key,
                thresholds.get(modality),
                allow_static=allow_static,
            )
        )
    if require_all:
        matched = all(result["matched"] for result in results)
    else:
        matched = any(result["matched"] for result in results)
    return {
        "identity_id": record["identity_id"],
        "results": results,
        "matched": matched,
    }




