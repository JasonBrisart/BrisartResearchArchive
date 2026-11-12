"""
File: entitle/revocation_list.py

Purpose
-------
Carry revocation to machines that never see the record log. The issuer publishes a signed
  revocation list (the entitlement IDs currently revoked, from the record log) and hands it to
  labs the same way as an entitlement, on a USB stick or a shared folder; a protected program or
  "run.py verify --revocation-list" then refuses a revoked entitlement on its own, offline. The
  list is signed, so a lab can read it but cannot edit it.

Communication / relationships
-----------------------------
Imports entitle/common.py (require_identifier, utc_now_iso, write_text_atomically),
  entitle/revoke.py (revoked_entitlements, revocation_record_count) and entitle/signing.py
  (sign_document, open_document, SignatureRejected); the RecordStore and keys are passed in.
  Imported by entitle/entitlements.py (load_revocation_list, during verification), cli.py
  (revoke publish) and gui/tabs.py (Revoke / Reinstate tab). Covered by
  tests/test_revocation_list.py.

Settings / parameters
---------------------
The payload is format entitle.revocation-list.v1 with issuer_id, sequence, published_at and
  revoked: a list of {entitlement_id, revoked_at, reason} sorted by ID. sequence is the number of
  revocation and reinstatement records in the log when the list was published, so a later list
  from the same log always has a higher number. The document kind is "revocation-list".

Edge cases
----------
publish_revocation_list includes revocations recorded for the given issuer and those recorded
  with no issuer, and leaves out IDs whose latest record is a reinstatement. An empty list is
  valid and useful: it proves nothing is revoked as of its sequence. load_revocation_list raises
  SignatureRejected for a list signed by an untrusted key, a broken signature, a different
  issuer (wrong_issuer) or a payload that is not a revocation list (payload_invalid).

Known limitations
-----------------
A list says what was revoked when it was published; a machine that is never given a newer list
  never learns of later revocations, and a machine can be handed an older list unless it keeps
  HostState (entitle/host.py), which refuses a sequence lower than one it has seen. Publishing
  from two different copies of the log can give sequences that do not increase; publish from
  one log.

Examples
--------
From the directory containing run.py (with a key pair from entitle/signing.py):

    from entitle.records import RecordStore
    from entitle.revoke import revoke
    from entitle.revocation_list import load_revocation_list, publish_revocation_list

    store = RecordStore("records/entitle_records.log")
    revoke(store, "lab-a-001", issuer_id="Issuer", reason="key compromise")
    publish_revocation_list(store, signing_key, issuer="Issuer", output="revoked.entitle-crl")
    listing = load_revocation_list("revoked.entitle-crl", [public_key], issuer="Issuer")
    assert "lab-a-001" in listing.revoked
"""
from dataclasses import dataclass
from pathlib import Path

from .common import require_identifier, utc_now_iso, write_text_atomically
from .revoke import revocation_record_count, revoked_entitlements
from .signing import SignatureRejected, open_document, sign_document

REVOCATION_LIST_FORMAT = "entitle.revocation-list.v1"
KIND = "revocation-list"
MAX_FILE_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class RevocationList:
    issuer_id: str
    sequence: int
    published_at: str
    revoked: dict
    key_id: str

    def reason_for(self, entitlement_id):
        entry = self.revoked.get(entitlement_id)
        return entry.get("reason") if entry else None


def publish_revocation_list(store, signing_key, *, issuer, output, overwrite=True):
    require_identifier(issuer=issuer)
    revoked = revoked_entitlements(store, issuer_id=issuer)
    payload = {
        "format": REVOCATION_LIST_FORMAT,
        "issuer_id": issuer,
        "sequence": revocation_record_count(store),
        "published_at": utc_now_iso(),
        "revoked": [
            {"entitlement_id": entitlement_id, "revoked_at": record.get("created_at"),
             "reason": record["data"].get("reason")}
            for entitlement_id, record in sorted(revoked.items())
        ],
    }
    write_text_atomically(output, sign_document(KIND, payload, signing_key), overwrite=overwrite)
    return payload


def load_revocation_list(path, trusted_keys, *, issuer):
    path = Path(path)
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"{path.name} is too large to be a revocation list.")
    text = path.read_bytes().decode("utf-8-sig", errors="replace")
    payload, key = open_document(text, KIND, trusted_keys)
    entries = payload.get("revoked")
    sequence = payload.get("sequence")
    if (
        payload.get("format") != REVOCATION_LIST_FORMAT
        or not isinstance(entries, list)
        or not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or not all(isinstance(e, dict) and isinstance(e.get("entitlement_id"), str) for e in entries)
    ):
        raise SignatureRejected("payload_invalid", f"{path.name} is not an Entitle revocation list.")
    if payload.get("issuer_id") != issuer:
        raise SignatureRejected("wrong_issuer", f"{path.name} was published for issuer {payload.get('issuer_id')!r}.")
    return RevocationList(
        issuer_id=issuer,
        sequence=sequence,
        published_at=payload.get("published_at"),
        revoked={entry["entitlement_id"]: entry for entry in entries},
        key_id=key.key_id,
    )
