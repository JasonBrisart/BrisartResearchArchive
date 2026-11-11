"""
File: entitle/entitlements.py

Purpose
-------
Own the .entitle file from end to end: what is inside one (a payload sealed with BSR2 for one
  issuer, subject and product), how it is written and read, and the three things an operator
  does with one: issue it, verify it, and migrate one written before Entitle 0.5.0 to the
  current encryption. The command line, the window, deployment tracking and the example
  application all go through these functions, so they cannot disagree about the file.

Communication / relationships
-----------------------------
Imports the entitle package root (EntitleError, canonical_json, require_text, utc_now_iso),
  entitle/rights.py (payload, rights and evaluation) and entitle/encryption.py (require, the
  linked BSR2 library; nothing else here touches 97_Encryption). Imported by cli.py (issue,
  verify, migrate), gui/tabs.py (Issue and Verify tabs), entitle/tracking.py
  (verify_entitlement, for deploy_from_file) and examples/protected_app_example.py
  (verify_entitlement). Covered by tests/test_entitlements.py.

Settings / parameters
---------------------
A file is BSR2 sealed format 3 (suite BSR2-S64-SIV) with 256-byte block padding, written as
  armored text from "-----BEGIN BSR2 SEALED MESSAGE-----" to "-----END BSR2 SEALED
  MESSAGE-----". Files written by Entitle before 0.5.0 are BSR2 Alpha 3 JSON envelopes
  (BSR2-ARX-SPONGE-ETM version 2) and are read but never written. The encryption context is
  make_context(product, issuer, subject): compact sorted JSON over system "Entitle", format
  ENTITLEMENT_FORMAT, product_id, issuer_id and subject_id; it is identical for both formats
  and must never change. master_key, drbg_seed and drbg_personalization may be text (UTF-8) or
  bytes. The master key is used directly as the BSR2 key and must be 32 to 1024 bytes. The
  optional DRBG seed (64 bytes or more) and personalization (16 or more) add a generator of the
  caller's choosing on top of the fresh system entropy BSR2 always uses; neither is needed, and
  a personalization without a seed is seeded from system entropy. MAX_PAYLOAD_BYTES (64 KiB)
  caps what open_entitlement decrypts. issue_entitlement also takes expires (ISO timestamp),
  the rights flags enterprise, modify, fork, export_source and redistribute, deployment_limit
  (default 1) and support_tier (default "standard").

Edge cases
----------
issue_entitlement checks its inputs before sealing or writing anything: a blank issuer,
  subject, product or entitlement ID, an expiry that is not an ISO timestamp, or a deployment
  limit that is negative or not a whole number raises ValueError. A limit of 0 is allowed: the
  entitlement verifies (for example to unlock features) but permits no tracked deployment.
  Sealing failures, including a short or oversized key, seed or personalization, raise
  EntitleBSRError carrying BSR2's reason. open_entitlement never raises for a bad file: a wrong
  key, issuer, subject or product, a modified, truncated or oversized file, and a payload that
  is not a JSON object all return (None, previous). verify_entitlement turns that into a denied
  result with reason bsr_verification_failed, raises FileNotFoundError for a missing file and
  ValueError for a file that is neither format, and raises EncryptionNotFoundError (never a
  denial) when 97_Encryption cannot be linked. write_entitlement_file writes beside the target
  and replaces it in one step, so a failure never leaves a half-written file. migrate_entitlement
  leaves a current file untouched (reason already_current_encryption); for a previous-format
  file it opens it, seals the same payload again, checks the new text opens to the identical
  payload, and only then replaces the file. A file that does not open with the given values
  raises EntitleError and is not changed. Migration judges nothing: an expired or revoked
  entitlement migrates like any other.

Known limitations
-----------------
The master key is not stretched, so a guessable key gives guessable protection. Files written
  here cannot be opened by Entitle versions before 0.5.0, and migration replaces the file in place;
  keep a copy first if an older Entitle must still read it. No date is set for dropping the
  previous format. Verification does not consult revocation; that is enforced when deploying.
  Neither interface can issue an unlimited deployment limit (None), although verification and
  deployment honor one. An expiry already in the past is accepted and the file is denied as
  entitlement_expired from the start.

Examples
--------
From the directory containing main.py:

    from tempfile import TemporaryDirectory
    from entitle.entitlements import issue_entitlement, verify_entitlement

    key = "a-master-key-that-is-at-least-32-bytes-long"
    with TemporaryDirectory() as folder:
        path = f"{folder}/demo.entitle"
        issue_entitlement(issuer="Issuer", subject="Lab", product="Demo", entitlement_id="e-1",
                          master_key=key, output=path, modify=True)
        result = verify_entitlement(issuer="Issuer", subject="Lab", product="Demo",
                                    master_key=key, path=path)
        assert result.allowed and result.has_right("can_modify")
"""

import json
import os
from pathlib import Path

from . import EntitleError, canonical_json, require_text, utc_now_iso
from .encryption import require
from .rights import (
    ENTITLEMENT_FORMAT,
    EntitlementResult,
    evaluate_payload,
    load_entitlement_payload,
    make_entitlement_payload,
    make_rights,
    parse_iso_datetime,
)

MAX_PAYLOAD_BYTES = 64 * 1024
ARMOR_BEGIN = "-----BEGIN BSR2 SEALED MESSAGE-----"
_ENVELOPE_START = "{"
_DEFAULT_PERSONALIZATION = b"Entitle/BSR2/entitlement/v1"


class EntitleBSRError(EntitleError):
    """Raised when BSR2 cannot seal an entitlement."""


# The .entitle file -----------------------------------------------------------------------------


def make_context(product, issuer, subject):
    return json.dumps(
        {
            "system": "Entitle",
            "format": ENTITLEMENT_FORMAT,
            "product_id": product,
            "issuer_id": issuer,
            "subject_id": subject,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _as_bytes(value):
    return value if isinstance(value, bytes) else value.encode("utf-8")


def _master_key(bsr2, master_key):
    key = _as_bytes(master_key)
    if len(key) < bsr2.aead.MIN_KEY_BYTES:
        raise EntitleBSRError(f"master key must contain at least {bsr2.aead.MIN_KEY_BYTES} bytes")
    if len(key) > bsr2.aead.MAX_KEY_BYTES:
        raise EntitleBSRError(f"master key must contain at most {bsr2.aead.MAX_KEY_BYTES} bytes")
    return key


def _generator(bsr2, seed, personalization):
    if not seed and not personalization:
        return None
    custom = _as_bytes(personalization) if personalization else _DEFAULT_PERSONALIZATION
    if not seed:
        return bsr2.drbg.BrisartDRBG.from_system_entropy(custom)
    return bsr2.drbg.BrisartDRBG(_as_bytes(seed), custom)


def is_previous_encryption(text):
    """True for the text of a file written by an Entitle before 0.5.0."""
    return text.lstrip().startswith(_ENVELOPE_START)


def seal_entitlement(payload, *, master_key, drbg_seed=None, drbg_personalization=None):
    """Return the text of a .entitle file holding payload, in the current format."""
    bsr2 = require()
    context = make_context(payload["product_id"], payload["issuer_id"], payload["subject_id"])
    try:
        sealed = bsr2.aead.seal(
            _master_key(bsr2, master_key),
            canonical_json(payload),
            context,
            rng=_generator(bsr2, drbg_seed, drbg_personalization),
            padding="block",
        )
        return bsr2.aead.armor(sealed)
    except Exception as exc:
        raise EntitleBSRError(f"BSR2 encryption failed: {exc}") from exc


def open_entitlement(text, *, master_key, issuer, subject, product):
    """Return (payload or None, previous_encryption) for the text of a .entitle file."""
    bsr2 = require()
    context = make_context(product, issuer, subject)
    previous = is_previous_encryption(text)
    try:
        key = _master_key(bsr2, master_key)
        if previous:
            plaintext = bsr2.envelope.decrypt(key, json.loads(text), context)
        else:
            plaintext = bsr2.aead.unseal(
                key, bsr2.aead.dearmor(text), context, max_plaintext_bytes=MAX_PAYLOAD_BYTES
            )
        return load_entitlement_payload(plaintext), previous
    except Exception:
        return None, previous


def write_entitlement_file(text, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_entitlement_file(path):
    path = Path(path)
    text = path.read_text(encoding="utf-8").strip()
    if not text.startswith(_ENVELOPE_START) and not text.startswith(ARMOR_BEGIN):
        raise ValueError(f"{path.name} is not a protected Entitle entitlement file.")
    return text


# Issue, verify, migrate ------------------------------------------------------------------------


def _check_issue_inputs(issuer, subject, product, entitlement_id, expires, deployment_limit):
    require_text(issuer=issuer, subject=subject, product=product, entitlement_id=entitlement_id)
    if expires:
        try:
            parse_iso_datetime(expires)
        except (TypeError, ValueError, AttributeError):
            raise ValueError(f"expires is not an ISO timestamp: {expires!r}") from None
    if deployment_limit is not None and (
        isinstance(deployment_limit, bool) or not isinstance(deployment_limit, int) or deployment_limit < 0
    ):
        raise ValueError("deployment limit must be a whole number of 0 or more.")


def issue_entitlement(
    *,
    issuer,
    subject,
    product,
    entitlement_id,
    master_key,
    output,
    expires=None,
    enterprise=False,
    modify=False,
    fork=False,
    export_source=False,
    redistribute=False,
    deployment_limit=1,
    support_tier="standard",
    drbg_seed=None,
    drbg_personalization=None,
):
    _check_issue_inputs(issuer, subject, product, entitlement_id, expires, deployment_limit)
    payload = make_entitlement_payload(
        issuer_id=issuer,
        subject_id=subject,
        product_id=product,
        entitlement_id=entitlement_id,
        issued_at=utc_now_iso(),
        expires_at=expires,
        rights=make_rights(
            enterprise=enterprise,
            modify=modify,
            fork=fork,
            export_source=export_source,
            redistribute=redistribute,
            deployment_limit=deployment_limit,
            support_tier=support_tier,
        ),
        metadata={
            "created_by": "Entitle",
            "protection": "BSR2-S64-SIV sealed message",
            "note": "Offline protected entitlement container.",
        },
    )
    write_entitlement_file(
        seal_entitlement(
            payload, master_key=master_key, drbg_seed=drbg_seed, drbg_personalization=drbg_personalization
        ),
        output,
    )
    return payload


def verify_entitlement(*, issuer, subject, product, master_key, path):
    payload, _ = open_entitlement(
        read_entitlement_file(path), master_key=master_key, issuer=issuer, subject=subject, product=product
    )
    if payload is None:
        return EntitlementResult.denied_result("bsr_verification_failed")
    return evaluate_payload(payload, expected_product_id=product)


def uses_previous_encryption(path):
    return is_previous_encryption(read_entitlement_file(path))


def migrate_entitlement(*, issuer, subject, product, master_key, path):
    text = read_entitlement_file(path)
    if not is_previous_encryption(text):
        return {"migrated": False, "reason": "already_current_encryption", "entitlement_id": None}
    identity = dict(master_key=master_key, issuer=issuer, subject=subject, product=product)
    payload, _ = open_entitlement(text, **identity)
    if payload is None:
        raise EntitleError(
            f"{path} does not open with this issuer, subject, product and master key. Nothing was changed."
        )
    migrated = seal_entitlement(payload, master_key=master_key)
    if open_entitlement(migrated, **identity) != (payload, False):
        raise EntitleError(f"The re-sealed copy of {path} did not open to the same entitlement. Nothing was changed.")
    write_entitlement_file(migrated, path)
    return {"migrated": True, "reason": "migrated", "entitlement_id": payload.get("entitlement_id")}
