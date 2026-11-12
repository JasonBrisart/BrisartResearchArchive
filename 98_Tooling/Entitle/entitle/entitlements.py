"""
File: entitle/entitlements.py

Purpose
-------
Own the .entitle file from end to end: its three formats, how it is written and read, and what
  an operator does with one: issue it, verify it, inspect it, and migrate it. A signed
  entitlement (Ed25519, the recommended format) can be verified with the issuer's public key
  alone, so a verifier can never forge one. A shared-key entitlement (sealed with BSR2 under a
  master key) is kept for compatibility: whoever can verify it can also issue it. Verification
  is the one place every offline check meets: authenticity, identity, validity window, machine
  binding, clock rollback and revocation. The command line, the window, deployment tracking and
  the example application all call these functions, so they cannot disagree about a file.

Communication / relationships
-----------------------------
Imports entitle/common.py (EntitleError, canonical_json, require_identifier, require_text,
  utc_now_iso, write_text_atomically), entitle/rights.py (payload, rights, evaluation),
  entitle/encryption.py (require, the linked BSR2, for shared-key files), entitle/signing.py
  (signed documents), entitle/host.py (machine_fingerprint, is_fingerprint), entitle/revoke.py
  (is_revoked, for a record log given at verification) and entitle/revocation_list.py
  (load_revocation_list). Imported by cli.py, gui/tabs.py, entitle/tracking.py
  (verify_entitlement) and examples/protected_app_example.py. Covered by
  tests/test_entitlements.py.

Settings / parameters
---------------------
Formats, told apart by their first line: signed ("-----BEGIN ENTITLE SIGNED ENTITLEMENT-----",
  payload format entitle.entitlement.v2, see entitle/signing.py); sealed ("-----BEGIN BSR2 SEALED
  MESSAGE-----", BSR2-S64-SIV with 256-byte block padding, payload entitle.entitlement.v1); and
  previous (a BSR2 Alpha 3 JSON envelope written before 0.5.0, read but never written). A sealed
  file's encryption context is make_context(product, issuer, subject) and must never change.
  issue_entitlement takes exactly one of signing_key (a SigningKey) or master_key (32 to 1024
  bytes, used directly as the BSR2 key), plus expires and, signed only, not_before (ISO
  timestamps; a date alone means 00:00 UTC that day) and machines (fingerprints from
  entitle/host.py); the rights flags; deployment_limit (default 1, None for unlimited);
  support_tier; the optional shared-key DRBG seed (64+ bytes) and personalization (16+ bytes);
  and overwrite (default False). verify_entitlement takes public_keys (a list of PublicKey) for a
  signed file or master_key for a shared-key one, and optionally revocation_list (a path or
  RevocationList), store (a RecordStore), machine_id, host_state (a HostState) and now.
  MAX_PAYLOAD_BYTES (64 KiB) caps what is opened and MAX_FILE_BYTES (1 MiB) what is read.

Edge cases
----------
issue_entitlement checks everything before writing anything: a blank issuer, subject or
  product, an entitlement ID that is blank or has spaces at either end, an unparseable expiry
  or not-before, a not-before at or after the expiry, a negative or non-integer limit, something
  that is not a machine fingerprint, not-before or machines on a shared-key file, a payload over
  the cap, an existing output file without overwrite, and neither or both of the two keys.
  verify_entitlement returns a denied result, never an exception, for a file that does not
  authenticate (signature_invalid, unknown_signing_key, malformed_entitlement for signed;
  bsr_verification_failed for shared-key) and for every rule in entitle/rights.py, then for
  clock_rollback_detected, entitlement_revoked, revocation_list_invalid (a list that does not
  verify or names another issuer: fail closed) and revocation_list_rollback. It raises
  ValueError for the wrong kind of key (a signed file with no public key, a shared-key file with
  no master key, a revocation list with no public key), FileNotFoundError for a missing file,
  ValueError for a file that is no format, over 1 MiB, or UTF-16 (which PowerShell's > writes),
  and EncryptionNotFoundError when 97_Encryption cannot be linked. A byte-order mark and Windows
  line endings are accepted. When an entitlement is bound to machines and no machine_id is
  given, this machine's fingerprint is computed. migrate_entitlement re-seals a previous-format
  file in the current sealed format, or with signing_key converts any shared-key file to signed
  (keeping the ID, rights, limit, issue time and expiry); it checks the new file opens to the
  same entitlement before replacing the old one, and leaves a file that does not open, or is
  already current or signed, untouched.

Known limitations
-----------------
A shared-key master key is not stretched and must be held by every verifier. verify does not
  consult revocation unless given a revocation list or a record log, and a machine that is never
  given a newer list does not learn of later revocations. Signed files cannot be read by Entitle
  before 0.7.0, nor sealed files by Entitle before 0.5.0; migration replaces the file in place.
  An expiry already in the past is accepted at issue. Replacing a file through a symbolic link
  replaces the link.

Examples
--------
From the directory containing run.py (keys from entitle/signing.py):

    from entitle.entitlements import issue_entitlement, verify_entitlement

    issue_entitlement(issuer="Issuer", subject="Lab", product="Demo", entitlement_id="e-1",
                      signing_key=signing_key, output="lab.entitle", modify=True)
    result = verify_entitlement(issuer="Issuer", subject="Lab", product="Demo",
                                public_keys=[public_key], path="lab.entitle")
    assert result.allowed and result.has_right("can_modify")
"""

import json
from pathlib import Path

from . import host
from .common import EntitleError, canonical_json, require_identifier, require_text, utc_now_iso, write_text_atomically
from .encryption import require
from .revocation_list import RevocationList, load_revocation_list
from .revoke import is_revoked
from .rights import (
    ENTITLEMENT_FORMAT,
    SIGNED_ENTITLEMENT_FORMAT,
    EntitlementResult,
    evaluate_payload,
    load_entitlement_payload,
    make_entitlement_payload,
    make_rights,
    parse_iso_datetime,
)
from .signing import SignatureRejected, is_signed_document, open_document, peek_document, sign_document

MAX_PAYLOAD_BYTES = 64 * 1024
MAX_FILE_BYTES = 1024 * 1024
ARMOR_BEGIN = "-----BEGIN BSR2 SEALED MESSAGE-----"
SIGNED_BEGIN = "-----BEGIN ENTITLE SIGNED ENTITLEMENT-----"
KIND = "entitlement"
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


def is_signed(text):
    """True for the text of a signed (Ed25519) entitlement."""
    return is_signed_document(text, KIND)


def file_format(text):
    """"signed", "sealed" (shared key, current encryption) or "previous" (shared key, before 0.5.0)."""
    if is_signed(text):
        return "signed"
    return "previous" if is_previous_encryption(text) else "sealed"


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


def _previous_envelope(text):
    """The parsed previous-format envelope, or None when it is not one or is too large to open."""
    envelope = json.loads(text)
    if not isinstance(envelope, dict):
        return None
    ciphertext = envelope.get("ciphertext")
    if isinstance(ciphertext, str) and len(ciphertext) > 2 * MAX_PAYLOAD_BYTES:
        return None
    return envelope


def open_entitlement(text, *, master_key, issuer, subject, product):
    """Return (payload or None, previous_encryption) for the text of a .entitle file."""
    bsr2 = require()
    context = make_context(product, issuer, subject)
    previous = is_previous_encryption(text)
    try:
        key = _master_key(bsr2, master_key)
        if previous:
            envelope = _previous_envelope(text)
            if envelope is None:
                return None, previous
            plaintext = bsr2.envelope.decrypt(key, envelope, context)
        else:
            plaintext = bsr2.aead.unseal(
                key, bsr2.aead.dearmor(text), context, max_plaintext_bytes=MAX_PAYLOAD_BYTES
            )
        return load_entitlement_payload(plaintext), previous
    except Exception:
        return None, previous


def write_entitlement_file(text, path, *, overwrite=True):
    write_text_atomically(path, text, overwrite=overwrite)


def read_entitlement_file(path):
    path = Path(path)
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"{path.name} is too large to be an entitlement file (over {MAX_FILE_BYTES // 1024} KiB).")
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise ValueError(
            f"{path.name} is UTF-16 text, which Windows PowerShell's > and Out-File produce. "
            "Copy the original file instead, or save it again as UTF-8."
        )
    try:
        text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n").strip()
    except UnicodeDecodeError:
        text = ""
    if not text.startswith((_ENVELOPE_START, ARMOR_BEGIN, SIGNED_BEGIN)):
        raise ValueError(f"{path.name} is not a protected Entitle entitlement file.")
    return text


# Issue, verify, migrate ------------------------------------------------------------------------


def _check_timestamp(name, value):
    if value:
        try:
            parse_iso_datetime(value)
        except (TypeError, ValueError, AttributeError):
            raise ValueError(f"{name} is not an ISO timestamp: {value!r}") from None


def _check_issue_inputs(issuer, subject, product, entitlement_id, expires, not_before, deployment_limit, machines):
    require_text(issuer=issuer, subject=subject, product=product)
    require_identifier(entitlement_id=entitlement_id)
    _check_timestamp("expires", expires)
    _check_timestamp("not before", not_before)
    if expires and not_before and parse_iso_datetime(not_before) >= parse_iso_datetime(expires):
        raise ValueError("not before must be earlier than expires.")
    if deployment_limit is not None and (
        isinstance(deployment_limit, bool) or not isinstance(deployment_limit, int) or deployment_limit < 0
    ):
        raise ValueError("deployment limit must be a whole number of 0 or more.")
    for machine in machines or []:
        if not host.is_fingerprint(machine):
            raise ValueError(f"{machine!r} is not a machine fingerprint (run 'python run.py fingerprint' on that machine).")


def issue_entitlement(
    *,
    issuer,
    subject,
    product,
    entitlement_id,
    output,
    master_key=None,
    signing_key=None,
    expires=None,
    not_before=None,
    machines=None,
    enterprise=False,
    modify=False,
    fork=False,
    export_source=False,
    redistribute=False,
    deployment_limit=1,
    support_tier="standard",
    drbg_seed=None,
    drbg_personalization=None,
    overwrite=False,
):
    """Issue a signed entitlement (signing_key) or a shared-key sealed one (master_key)."""
    if (signing_key is None) == (master_key is None or master_key == ""):
        raise ValueError("give either a signing key (signed entitlement, recommended) or a master key (shared-key).")
    _check_issue_inputs(issuer, subject, product, entitlement_id, expires, not_before, deployment_limit, machines)
    if not overwrite and Path(output).exists():
        raise FileExistsError(f"{output} already exists. Choose another path, or overwrite it on purpose.")
    signed = signing_key is not None
    payload = make_entitlement_payload(
        issuer_id=issuer,
        subject_id=subject,
        product_id=product,
        entitlement_id=entitlement_id,
        issued_at=utc_now_iso(),
        expires_at=expires,
        signed=signed,
        not_before=not_before,
        machines=machines,
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
            "protection": "Ed25519 signature" if signed else "BSR2-S64-SIV sealed message",
            "note": "Offline entitlement.",
            **({"signing_key_id": signing_key.key_id} if signed else {}),
        },
    )
    size = len(canonical_json(payload))
    if size > MAX_PAYLOAD_BYTES:
        raise ValueError(
            f"the entitlement is {size:,} bytes, over the {MAX_PAYLOAD_BYTES:,} byte limit that verification "
            "accepts. Shorten the longest field (the entitlement ID, support tier or a name)."
        )
    if signed:
        text = sign_document(KIND, payload, signing_key)
    else:
        text = seal_entitlement(
            payload, master_key=master_key, drbg_seed=drbg_seed, drbg_personalization=drbg_personalization
        )
    write_entitlement_file(text, output, overwrite=overwrite)
    return payload


def _open_signed(text, public_keys):
    try:
        payload, key = open_document(text, KIND, public_keys)
    except SignatureRejected as rejected:
        reason = "malformed_entitlement" if rejected.reason == "not_signed_document" else rejected.reason
        return None, None, reason
    if len(canonical_json(payload)) > MAX_PAYLOAD_BYTES:
        return None, None, "malformed_entitlement"
    if payload.get("format") != SIGNED_ENTITLEMENT_FORMAT:
        return None, None, "unsupported_entitlement_format"
    return payload, key, None


def _revocation_denial(payload, public_keys, revocation_list, store, host_state):
    entitlement_id = payload.get("entitlement_id")
    if revocation_list is not None:
        listing = revocation_list
        if not isinstance(listing, RevocationList):
            if not public_keys:
                raise ValueError("a revocation list is signed; give the issuer's public key to check it.")
            try:
                listing = load_revocation_list(listing, public_keys, issuer=payload.get("issuer_id"))
            except SignatureRejected:
                return "revocation_list_invalid"
        if listing.issuer_id != payload.get("issuer_id"):
            return "revocation_list_invalid"
        if host_state is not None:
            rollback = host_state.check_revocation_sequence(listing.key_id, listing.sequence)
            if rollback:
                return rollback
        if entitlement_id in listing.revoked:
            return "entitlement_revoked"
    if store is not None and is_revoked(store, entitlement_id):
        return "entitlement_revoked"
    return None


def verify_entitlement(
    *,
    issuer,
    subject,
    product,
    path,
    master_key=None,
    public_keys=None,
    revocation_list=None,
    store=None,
    machine_id=None,
    host_state=None,
    now=None,
):
    """Authenticate the file, then judge it. Returns an EntitlementResult; denials never raise.

    A signed file needs public_keys (PublicKey objects); a shared-key file needs master_key.
    revocation_list (a path or RevocationList), store (a RecordStore) and host_state
    (entitle.host.HostState) add offline revocation, clock-rollback and list-rollback checks.
    """
    text = read_entitlement_file(path)
    signed_by = None
    if is_signed(text):
        if not public_keys:
            raise ValueError(f"{Path(path).name} is a signed entitlement; check it with the issuer's public key.")
        payload, key, problem = _open_signed(text, public_keys)
        if problem:
            return EntitlementResult.denied_result(problem)
        signed_by = key.key_id
    else:
        if not master_key:
            raise ValueError(f"{Path(path).name} is a shared-key entitlement; it needs the master key it was issued with.")
        payload, _ = open_entitlement(text, master_key=master_key, issuer=issuer, subject=subject, product=product)
        if payload is None:
            return EntitlementResult.denied_result("bsr_verification_failed")
    if host_state is not None:
        rolled_back = host_state.check_clock(now)
        if rolled_back:
            return EntitlementResult.denied_result(rolled_back, payload)
    machines = payload.get("machines") or []
    if machines and machine_id is None:
        machine_id = host.machine_fingerprint()
    result = evaluate_payload(
        payload, expected_product_id=product, expected_issuer_id=issuer, expected_subject_id=subject,
        machine_id=machine_id, now=now,
    )
    if result.allowed:
        denial = _revocation_denial(payload, public_keys, revocation_list, store, host_state)
        if denial:
            result = EntitlementResult.denied_result(denial, payload)
    result.signed_by = signed_by
    return result


def uses_previous_encryption(path):
    return is_previous_encryption(read_entitlement_file(path))


def inspect_entitlement(path):
    """What can be said about a file without any key. A signed payload is shown UNVERIFIED."""
    text = read_entitlement_file(path)
    kind = file_format(text)
    details = {"file": str(path), "format": kind, "verified": False}
    if kind == "signed":
        try:
            payload, key_id = peek_document(text, KIND)
        except SignatureRejected as rejected:
            details["problem"] = str(rejected)
        else:
            details.update(signing_key_id=key_id, payload=payload)
    else:
        details["note"] = "A shared-key entitlement is encrypted; only the master key can show what it grants."
    return details


def migrate_entitlement(*, issuer, subject, product, master_key, path, signing_key=None):
    """Re-seal a pre-0.5.0 file in the current format, or (signing_key) convert any shared-key file to signed."""
    text = read_entitlement_file(path)
    if is_signed(text):
        return {"migrated": False, "reason": "already_signed", "entitlement_id": None}
    if signing_key is None and not is_previous_encryption(text):
        return {"migrated": False, "reason": "already_current_encryption", "entitlement_id": None}
    identity = dict(master_key=master_key, issuer=issuer, subject=subject, product=product)
    payload, _ = open_entitlement(text, **identity)
    if payload is None:
        raise EntitleError(
            f"{path} does not open with this issuer, subject, product and master key. Nothing was changed."
        )
    if signing_key is None:
        migrated = seal_entitlement(payload, master_key=master_key)
        if open_entitlement(migrated, **identity) != (payload, False):
            raise EntitleError(f"The re-sealed copy of {path} did not open to the same entitlement. Nothing was changed.")
        reason = "migrated"
    else:
        converted = {
            **payload,
            "format": SIGNED_ENTITLEMENT_FORMAT,
            "not_before": None,
            "machines": [],
            "metadata": {**payload.get("metadata", {}), "protection": "Ed25519 signature",
                         "signing_key_id": signing_key.key_id, "converted_from": "shared-key"},
        }
        migrated = sign_document(KIND, converted, signing_key)
        reopened, _, problem = _open_signed(migrated, [signing_key.public])
        unchanged = ("issuer_id", "subject_id", "product_id", "entitlement_id", "issued_at", "expires_at", "rights")
        if problem or any(reopened.get(field) != payload.get(field) for field in unchanged):
            raise EntitleError(f"The signed copy of {path} did not open to the same entitlement. Nothing was changed.")
        reason = "converted_to_signed"
    write_entitlement_file(migrated, path)
    return {"migrated": True, "reason": reason, "entitlement_id": payload.get("entitlement_id")}
