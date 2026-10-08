"""
Entitle BSR Adapter

Connects Entitle to BrisartSecurityResearch (BSR2).

Expected behavior:
    - Entitle creates plain JSON entitlement payloads.
    - BSR encrypts/authenticates them into protected envelopes.
    - BSR verifies authentication before returning plaintext.
    - If BSR verification fails, Entitle denies governed rights.

Important:
    BrisartSecurityResearch is currently an experimental research implementation.
    Use this adapter for controlled, offline, internal, and research-oriented
    environments unless/until BSR receives independent review.

BSR2 itself lives in the sibling ``vendor/`` directory and is used completely
unmodified. Its own modules use flat, top-level imports
(e.g. ``from brisart_security_primitives import ...``), so the ``vendor/``
directory itself must be present on ``sys.path`` before this module is imported.
``entitle.bootstrap.ensure_bsr_on_path()`` handles that; every Entitle entry
point (CLI, GUI, examples) calls it before importing anything from this module.
"""
import json
from pathlib import Path
from .core import (
    canonical_json,
    evaluate_payload,
    load_entitlement_payload,
)

try:
    from brisart_security_drbg import BrisartDRBG as BrisartSecurityDRBG
    from brisart_security_envelope import encrypt as encrypt_envelope, decrypt as decrypt_envelope
except ImportError as exc:
    raise ImportError(
        "Could not import BrisartSecurityResearch (BSR2) modules. "
        "Make sure the 'vendor/' directory has been added to sys.path before "
        "importing entitle.bsr_adapter (see entitle.bootstrap.ensure_bsr_on_path)."
    ) from exc

ENTITLEMENT_CONTEXT_FORMAT = "entitle.entitlement.v1"


class EntitleBSRError(Exception):
    """Raised when BSR protection or verification fails."""


def make_context(product_id, issuer_id, subject_id):
    """
    Context binding prevents one entitlement envelope from being silently reused
    for another product/customer context.

    The same exact context must be supplied during encryption and decryption.
    """
    context = {
        "system": "Entitle",
        "format": ENTITLEMENT_CONTEXT_FORMAT,
        "product_id": product_id,
        "issuer_id": issuer_id,
        "subject_id": subject_id,
    }
    return json.dumps(
        context,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def make_drbg(seed, personalization):
    """
    Create the BSR DRBG instance.

    BSR requires caller-provided seed material and personalization. Its README
    states the DRBG expands caller-provided seed material and does not create
    entropy by itself.
    """
    return BrisartSecurityDRBG(
        seed=seed,
        personalization=personalization,
    )


def protect_entitlement_payload(
    *,
    payload,
    master_key,
    drbg_seed,
    drbg_personalization,
):
    """
    Convert an Entitle payload into an authenticated BSR envelope.
    """
    plaintext = canonical_json(payload)
    context = make_context(
        product_id=payload["product_id"],
        issuer_id=payload["issuer_id"],
        subject_id=payload["subject_id"],
    )
    drbg = make_drbg(
        seed=drbg_seed,
        personalization=drbg_personalization,
    )
    try:
        envelope = encrypt_envelope(
            master_key=master_key,
            plaintext=plaintext,
            context=context,
            rng=drbg,
        )
    except Exception as exc:
        raise EntitleBSRError("BSR envelope encryption failed.") from exc
    return envelope


def open_entitlement_envelope(
    *,
    envelope,
    master_key,
    expected_product_id,
    issuer_id,
    subject_id,
):
    """
    Open and verify a protected entitlement envelope.

    If the envelope was modified, malformed, encrypted for another context, or
    authenticated fields changed, BSR should fail before Entitle receives
    plaintext.
    """
    context = make_context(
        product_id=expected_product_id,
        issuer_id=issuer_id,
        subject_id=subject_id,
    )
    try:
        plaintext = decrypt_envelope(
            master_key=master_key,
            envelope=envelope,
            context=context,
        )
    except Exception:
        return None
    try:
        payload = load_entitlement_payload(plaintext)
    except Exception:
        return None
    return payload


def save_protected_entitlement(envelope, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(envelope, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def load_protected_entitlement(path):
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def verify_protected_entitlement(
    *,
    path,
    master_key,
    expected_product_id,
    issuer_id,
    subject_id,
):
    envelope = load_protected_entitlement(path)
    payload = open_entitlement_envelope(
        envelope=envelope,
        master_key=master_key,
        expected_product_id=expected_product_id,
        issuer_id=issuer_id,
        subject_id=subject_id,
    )
    if payload is None:
        from .core import EntitlementResult
        return EntitlementResult.denied_result("bsr_verification_failed")
    return evaluate_payload(
        payload,
        expected_product_id=expected_product_id,
    )
