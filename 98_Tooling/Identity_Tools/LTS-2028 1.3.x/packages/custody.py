"""
File: packages/custody.py

Purpose
-------
Tamper-evident chain of custody, embedded inside the package itself.

Public interface:
- class CustodyError(ValueError) -- Raised when a custody chain is malformed,
  invalid, or fails verification.
- new_chain(creator_label, package_id) -- Start a fresh custody chain with a
  single ``"created"`` entry.
- append(chain, action, actor_label, details=None) -- Return a new chain with
  one more entry appended.
- verify_chain(chain, package_id=None)
- summarize(chain) -- A compact, display-friendly summary of a custody chain's
  history.

Design notes:

Each entry commits to the previous entry's hash, so altering, deleting, or
reordering a past entry changes every hash after it -- the same tamper-evidence
property a git history or a blockchain-style hash chain relies on, implemented
here with nothing more than :mod:`common.hashing`.

The custody chain records events and checks their internal consistency;
it does not decide whether a recipient is authorized or unwrap encryption
keys. Those responsibilities belong to ``verification.py`` and ``ciphers.py``.

Communication / relationships
-----------------------------
Depends on (project modules):
- common.hashing (common/hashing.py)
- common.timestamps (common/timestamps.py)
Standard library: json.
Imported by:
- gui/tabs/tab_packages.py
- packages/main.py
- packages/package.py
Covered by tests: packages/tests/test_custody_chain.py,
packages/tests/test_package_integrity.py.

Settings / parameters
---------------------
- GENESIS_PREVIOUS_HASH = "0" * 64
- _VALID_ACTIONS = ('created', 'recipient_added', 'recipient_removed',
  'opened', 'payload_rewrapped')

Edge cases
----------
- _build_entry() raises CustodyError: "unsupported custody action {...};
  expected one of {...}."
- _build_entry() raises CustodyError: "actor_label must be a non-empty string."
- append() raises CustodyError: "cannot append to an empty custody chain."
- verify_chain() raises CustodyError: "custody chain must be a list."
- verify_chain() raises CustodyError: "custody chain cannot be empty."
- verify_chain() raises CustodyError: "every custody chain entry must be an
  object."
- verify_chain() raises CustodyError: "custody chain's first entry is not a
  genesis entry."
- verify_chain() raises CustodyError: "custody chain's first entry must be a
  'created' entry."
- verify_chain() raises CustodyError: "custody chain's genesis entry does not
  match this package's id."
- verify_chain() raises CustodyError: "custody chain is broken at entry {...}:
  previous_hash does not match the prior entry's recorded hash."
- verify_chain() raises CustodyError: "custody chain entry {...} has been
  tampered with: stored hash does not match its recomputed content."

Known limitations
-----------------
- Unlike ``audit.py`` (an external, append-only log of package events written
  to the filesystem), the custody chain travels *inside* the package's own
  state: every package carries its own history of who created it, who was added
  or removed as a recipient, and who opened it.
- This is integrity evidence, not access control: a broken chain tells you the
  package's history was edited after the fact, but the chain itself does not
  decide who is allowed to open the package.

Examples
--------
Run from the repository root.

::

    from packages.custody import append, new_chain, summarize, verify_chain

    chain = new_chain("Alice", "pkg-1")                  # one "created" entry
    chain = append(chain, "recipient_added", "Alice", {"identity_id": "bob"})
    chain = append(chain, "opened", "Bob")               # returns a new list

    print(verify_chain(chain, "pkg-1"))
    for entry in summarize(chain):
        print(entry["action"], entry["actor_label"])
"""

import json

from common.hashing import sha256_bytes
from common.timestamps import utc_now_iso

GENESIS_PREVIOUS_HASH = "0" * 64
_VALID_ACTIONS = (
    "created",
    "recipient_added",
    "recipient_removed",
    "opened",
    "payload_rewrapped",
)


class CustodyError(ValueError):
    """Raised when a custody chain is malformed, invalid, or fails
    verification."""


def _entry_hash(previous_hash: str, action: str, actor_label: str, recorded_at: str, details: dict) -> str:
    # A canonical (sorted-key, no-whitespace) JSON encoding of the entry's own
    # fields, so the same logical entry always hashes identically regardless
    # of how it was constructed.
    canonical = json.dumps(
        {
            "previous_hash": previous_hash,
            "action": action,
            "actor_label": actor_label,
            "recorded_at": recorded_at,
            "details": details,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(canonical)


def _build_entry(previous_hash: str, action: str, actor_label: str, details: dict = None) -> dict:
    if action not in _VALID_ACTIONS:
        raise CustodyError(f"unsupported custody action {action!r}; expected one of {_VALID_ACTIONS}.")
    if not isinstance(actor_label, str) or not actor_label:
        raise CustodyError("actor_label must be a non-empty string.")
    details = details or {}
    recorded_at = utc_now_iso()
    entry_hash = _entry_hash(previous_hash, action, actor_label, recorded_at, details)
    return {
        "previous_hash": previous_hash,
        "entry_hash": entry_hash,
        "action": action,
        "actor_label": actor_label,
        "recorded_at": recorded_at,
        "details": details,
    }


def new_chain(creator_label: str, package_id: str) -> list:
    """Start a fresh custody chain with a single ``"created"`` entry."""
    entry = _build_entry(
        GENESIS_PREVIOUS_HASH, "created", creator_label, {"package_id": package_id}
    )
    return [entry]


def append(chain: list, action: str, actor_label: str, details: dict = None) -> list:
    """Return a new chain with one more entry appended.

    A new list is returned rather than mutating ``chain`` in place, so a
    caller holding a reference to the pre-append chain (for comparison, or
    for an audit log entry) is not surprised by it changing underfoot.
    """
    if not chain:
        raise CustodyError("cannot append to an empty custody chain.")
    previous_hash = chain[-1]["entry_hash"]
    entry = _build_entry(previous_hash, action, actor_label, details)
    return list(chain) + [entry]


def verify_chain(chain: list, package_id: str = None) -> bool:
    # BUG FIX (see docs/BUGFIX_2026-08-24.md; same class of bug as the
    # 0.8.2-beta/0.4.0 CHANGELOG entries): earlier versions of this function
    # iterated `chain` and indexed `chain[0]` without first checking that
    # `chain` is actually a list and that each entry is actually a dict. A
    # hand-edited package carrying "custody_chain": 123 (a non-iterable)
    # raised a raw TypeError instead of the intended CustodyError, which let
    # a malformed package escape as an uncaught exception in open_package's
    # audit path instead of a clean, audited denial. These structural checks
    # are re-verified here rather than assumed, since validate_package's own
    # dict/list checks run before this but a caller could invoke verify_chain
    # directly.
    if not isinstance(chain, list):
        raise CustodyError("custody chain must be a list.")
    if not chain:
        raise CustodyError("custody chain cannot be empty.")
    if not all(isinstance(entry, dict) for entry in chain):
        raise CustodyError("every custody chain entry must be an object.")

    first = chain[0]
    if first.get("previous_hash") != GENESIS_PREVIOUS_HASH:
        raise CustodyError("custody chain's first entry is not a genesis entry.")
    if first.get("action") != "created":
        raise CustodyError("custody chain's first entry must be a 'created' entry.")
    if package_id is not None:
        if first.get("details", {}).get("package_id") != package_id:
            raise CustodyError(
                "custody chain's genesis entry does not match this package's id."
            )

    expected_previous = GENESIS_PREVIOUS_HASH
    for index, entry in enumerate(chain):
        if entry.get("previous_hash") != expected_previous:
            raise CustodyError(
                f"custody chain is broken at entry {index}: previous_hash does "
                "not match the prior entry's recorded hash."
            )
        recomputed = _entry_hash(
            entry["previous_hash"],
            entry["action"],
            entry["actor_label"],
            entry["recorded_at"],
            entry.get("details", {}),
        )
        if recomputed != entry.get("entry_hash"):
            raise CustodyError(
                f"custody chain entry {index} has been tampered with: stored "
                "hash does not match its recomputed content."
            )
        expected_previous = entry["entry_hash"]

    return True


def summarize(chain: list) -> list:
    """A compact, display-friendly summary of a custody chain's history."""
    return [
        {
            "action": entry["action"],
            "actor_label": entry["actor_label"],
            "recorded_at": entry["recorded_at"],
        }
        for entry in chain
    ]




