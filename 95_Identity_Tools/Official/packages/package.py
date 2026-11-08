"""
File: packages/package.py

Purpose
-------
Identity-Bound Package orchestration: create, add/remove recipients, open.

Public interface:
- class PackageError(ValueError) -- Raised for malformed package state or
  invalid arguments.
- class PackageAuthorizationError(ValueError) -- Raised when a supplied master
  key does not match the recipient it claims to belong to.
- create_package(package_id, creator_label, payload, recipients,
  audit_dir=None) -- Create a new package sealed for an initial set of
  recipients.
- validate_package(state) -- Validate a package's shape, raising
  :class:`PackageError` on failure.
- add_recipient(state, identity_id, label, master_key, opener_identity_id,
  opener_master_key, audit_dir=None) -- Add a new recipient to an existing
  package.
- remove_recipient(state, identity_id, opener_identity_id, opener_master_key,
  audit_dir=None) -- Remove a recipient from an existing package.
- open_package(state, identity_id, master_key, audit_dir=None) -- Open a
  package's payload as an authorized recipient.
- list_recipients(state) -- List every recipient's non-secret descriptor (id
  and label only).
- custody_summary(state) -- A compact, display-friendly summary of the
  package's custody history.
- recipient_key_from_text(state, identity_id, text) -- The master key that
  authenticates ``identity_id`` from typed text: the current text key, or the
  legacy one for a recipient not yet migrated.
- needs_encryption_migration(state, identity_id, text) -- Report whether this
  recipient's part of the package still uses the previous encryption.
- migrate_recipient(state, identity_id, text, audit_dir=None) -- Move this
  recipient's key slot and verifier, and the payload, to the current
  encryption. Returns the updated state.

Design notes:

Ties together every other module in ``packages/``:

- :mod:`packages.ciphers` for content-key generation and per-recipient key slot
  sealing/unwrapping,
- :mod:`packages.identity` for recipient descriptor shape,
- :mod:`packages.verification` for the fast "does this key belong to this
  recipient" check before touching a key slot,
- :mod:`packages.custody` for the package's own tamper-evident history,
- :mod:`packages.audit` for an external, durable trail of package events.

A package's on-disk/in-memory state is a single JSON-serialisable dict with
four parts: identifying metadata, the sealed payload, a map of recipient key
slots, and the custody chain. Nothing here performs file I/O directly --
persistence is left to the caller (typically ``main.py``), matching the
separation ``vault.store.vault_service`` keeps from ``vault.store.vault_file``.

Encryption migration. A package has one payload but one key slot and verifier
per recipient, each under that recipient's own master key, so it migrates one
recipient at a time: migrate_recipient() needs that recipient's typed text. It
recovers the content key through the slot (under the legacy text key if that is
what verifies), reseals the payload if it is still legacy, seals the slot and
builds the verifier under the current text key, and appends a
``payload_rewrapped`` custody entry with ``{"identity_id", "reason":
"encryption_migration"}``. The content key does not change, so recipients not
yet migrated keep opening the package with their legacy slots until they
migrate themselves.

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.context (crypto/context.py)
- crypto.envelope (crypto/envelope.py) -- is_legacy, reseal
- crypto.errors (crypto/errors.py)
- crypto.factors (crypto/factors.py) -- is_legacy_binding
- crypto.rng (crypto/rng.py)
- packages.audit (packages/audit.py)
- packages.ciphers (packages/ciphers.py)
- packages.custody (packages/custody.py)
- packages.identity (packages/identity.py)
- packages.verification (packages/verification.py)
Standard library: none.
Imported by:
- gui/tabs/tab_packages.py
- packages/demo.py
- packages/main.py
Covered by tests: gui/tests/test_tab_packages.py,
packages/tests/test_package_integrity.py, packages/tests/test_package_migration.py.

Settings / parameters
---------------------
- PACKAGE_FORMAT = "brisart-identity-tools/ibp-package/v1"

Edge cases
----------
- migrate_recipient() raises PackageAuthorizationError when the text does not
  authenticate the recipient under either text key, and changes nothing.
- needs_encryption_migration() returns False for an identity that is not a
  recipient, so callers fall through to the normal authorization error.
- create_package() raises PackageError: "package_id must be a non-empty
  string."
- create_package() raises PackageError: "at least one recipient is required."
- validate_package() raises PackageError: "package state must be an object."
- validate_package() raises PackageError: "unsupported package format."
- validate_package() raises PackageError: "package_id must be a non-empty
  string."
- validate_package() raises PackageError: "recipients must be an object."
- validate_package() raises PackageError: "key_slots must be an object."
- validate_package() raises PackageError: "recipients and key_slots must have
  matching identity ids."
- validate_package() raises PackageError: "payload must be an object."
- validate_package() raises PackageError: "custody_chain must be a non-empty
  list."
- add_recipient() raises PackageError: "recipient {...} is already in this
  package."
- remove_recipient() raises PackageError: "recipient {...} is not in this
  package."
- remove_recipient() raises PackageError: "cannot remove the last recipient; a
  package must always have at least one."
- _authorized_content_key() raises PackageAuthorizationError: "{...} is not a
  recipient of this package."
- _authorized_content_key() raises PackageAuthorizationError: "the supplied
  master key does not match recipient {...}."
- _authorized_content_key() raises PackageAuthorizationError: "key slot for
  {...} failed to authenticate: {...}"
- _authorized_content_key(): translates Bsr2IntegrationError into
  PackageAuthorizationError; other exceptions may still propagate.
- open_package(): catches PackageAuthorizationError for cleanup or bookkeeping,
  then re-raises it unchanged.

Known limitations
-----------------
- Security rests on BSR2, a custom research construction that has not been
  independently audited (see docs/SECURITY.md); do not treat it as a
  replacement for vetted, audited cryptography.

Examples
--------
Call shapes only, not a runnable script: package_id, creator_label, payload,
recipients, state, identity_id, label, master_key, opener_identity_id,
opener_master_key stand for values the caller supplies.

::

    from packages.package import (
        create_package,
        validate_package,
        add_recipient,
    )
    create_package(package_id, creator_label, payload, recipients)
    validate_package(state)
    add_recipient(
        state,
        identity_id,
        label,
        master_key,
        opener_identity_id,
        opener_master_key,
    )
"""

from crypto.context import package_context
from crypto.envelope import is_legacy, reseal
from crypto.errors import Bsr2IntegrationError
from crypto.factors import is_legacy_binding
from crypto.rng import new_generator
from packages import audit, ciphers, custody
# BUG FIX (2026-08-24): this previously also imported RecipientIdentityError
# and validate_identity_id from packages.identity, neither of which is
# referenced anywhere in this file (only new_recipient is actually called).
# Ruff's pyflakes rule (F401, enabled in pyproject.toml's `select`) flags
# unused imports and fails the lint job.
from packages.identity import new_recipient
from packages.verification import build_recipient_verifier, verify_recipient_master_key

PACKAGE_FORMAT = "brisart-identity-tools/ibp-package/v1"


class PackageError(ValueError):
    """Raised for malformed package state or invalid arguments."""


class PackageAuthorizationError(ValueError):
    """Raised when a supplied master key does not match the recipient it
    claims to belong to.

    Deliberately distinct from a key-slot authentication failure
    (:class:`crypto.errors.EnvelopeAuthenticationError`): this is caught
    earlier, before any key slot is touched, using the recipient verifier
    from ``verification.py``.
    """


def create_package(package_id: str, creator_label: str, payload: dict, recipients: dict, audit_dir=None) -> dict:
    """Create a new package sealed for an initial set of recipients.

    ``recipients`` maps ``identity_id -> (label, master_key)`` tuples. At
    least one recipient is required, since a package with zero recipients
    can never be opened by anyone.
    """
    if not isinstance(package_id, str) or not package_id:
        raise PackageError("package_id must be a non-empty string.")
    if not recipients:
        raise PackageError("at least one recipient is required.")

    content_key = ciphers.new_content_key()
    sealed_payload = ciphers.seal_payload(content_key, package_id, payload)

    key_slots = {}
    recipient_descriptors = {}
    for identity_id, (label, master_key) in recipients.items():
        descriptor = new_recipient(identity_id, label)
        verifier = build_recipient_verifier(master_key, identity_id)
        wrapped = ciphers.wrap_content_key(master_key, package_id, identity_id, content_key)
        recipient_descriptors[identity_id] = {**descriptor, "verifier": verifier}
        key_slots[identity_id] = wrapped

    chain = custody.new_chain(creator_label, package_id)

    state = {
        "format": PACKAGE_FORMAT,
        "package_id": package_id,
        "recipients": recipient_descriptors,
        "key_slots": key_slots,
        "payload": sealed_payload,
        "custody_chain": chain,
    }

    if audit_dir is not None:
        audit.record_event(audit_dir, "created", package_id, creator_label)

    return state


def validate_package(state: dict) -> dict:
    """Validate a package's shape, raising :class:`PackageError` on failure."""
    if not isinstance(state, dict):
        raise PackageError("package state must be an object.")
    if state.get("format") != PACKAGE_FORMAT:
        raise PackageError("unsupported package format.")
    if not isinstance(state.get("package_id"), str) or not state["package_id"]:
        raise PackageError("package_id must be a non-empty string.")
    if not isinstance(state.get("recipients"), dict):
        raise PackageError("recipients must be an object.")
    if not isinstance(state.get("key_slots"), dict):
        raise PackageError("key_slots must be an object.")
    if set(state["recipients"]) != set(state["key_slots"]):
        raise PackageError("recipients and key_slots must have matching identity ids.")
    if not isinstance(state.get("payload"), dict):
        raise PackageError("payload must be an object.")
    if not isinstance(state.get("custody_chain"), list) or not state["custody_chain"]:
        raise PackageError("custody_chain must be a non-empty list.")

    custody.verify_chain(state["custody_chain"], state["package_id"])
    return state


def add_recipient(state: dict, identity_id: str, label: str, master_key: bytes, opener_identity_id: str, opener_master_key: bytes, audit_dir=None) -> dict:
    """Add a new recipient to an existing package.

    The caller must supply an existing, authorized recipient's identity and
    master key (``opener_identity_id``/``opener_master_key``) to recover the
    content key -- a package's content key is never derivable from the
    package state alone, so adding a recipient always requires an existing
    one to authorize it.
    """
    state = validate_package(state)
    if identity_id in state["recipients"]:
        raise PackageError(f"recipient {identity_id!r} is already in this package.")

    content_key = _authorized_content_key(state, opener_identity_id, opener_master_key)

    descriptor = new_recipient(identity_id, label)
    verifier = build_recipient_verifier(master_key, identity_id)
    wrapped = ciphers.wrap_content_key(master_key, state["package_id"], identity_id, content_key)

    updated = dict(state)
    updated["recipients"] = dict(state["recipients"])
    updated["recipients"][identity_id] = {**descriptor, "verifier": verifier}
    updated["key_slots"] = dict(state["key_slots"])
    updated["key_slots"][identity_id] = wrapped
    updated["custody_chain"] = custody.append(
        state["custody_chain"], "recipient_added", label, {"identity_id": identity_id}
    )

    if audit_dir is not None:
        audit.record_event(audit_dir, "recipient_added", state["package_id"], label)

    return updated


def remove_recipient(state: dict, identity_id: str, opener_identity_id: str, opener_master_key: bytes, audit_dir=None) -> dict:
    """Remove a recipient from an existing package.

    The removed recipient's key slot is deleted; their master key (which the
    package never stored anyway) no longer opens this package. The payload
    is not re-encrypted and no other recipient's slot is touched.
    """
    state = validate_package(state)
    if identity_id not in state["recipients"]:
        raise PackageError(f"recipient {identity_id!r} is not in this package.")
    if len(state["recipients"]) == 1:
        raise PackageError(
            "cannot remove the last recipient; a package must always have "
            "at least one."
        )

    # Authorization check: the opener must themselves be an existing,
    # verified recipient, even if they are not the one being removed.
    _authorized_content_key(state, opener_identity_id, opener_master_key)

    removed_label = state["recipients"][identity_id]["label"]

    updated = dict(state)
    updated["recipients"] = dict(state["recipients"])
    del updated["recipients"][identity_id]
    updated["key_slots"] = dict(state["key_slots"])
    del updated["key_slots"][identity_id]
    updated["custody_chain"] = custody.append(
        state["custody_chain"], "recipient_removed", removed_label, {"identity_id": identity_id}
    )

    if audit_dir is not None:
        audit.record_event(audit_dir, "recipient_removed", state["package_id"], removed_label)

    return updated


def _authorized_content_key(state: dict, identity_id: str, master_key: bytes) -> bytes:
    """Verify a recipient and recover the content key, or raise."""
    recipient = state["recipients"].get(identity_id)
    if recipient is None:
        raise PackageAuthorizationError(
            f"{identity_id!r} is not a recipient of this package."
        )
    if not verify_recipient_master_key(master_key, identity_id, recipient["verifier"]):
        raise PackageAuthorizationError(
            f"the supplied master key does not match recipient {identity_id!r}."
        )
    wrapped = state["key_slots"][identity_id]
    try:
        return ciphers.unwrap_content_key(master_key, state["package_id"], identity_id, wrapped)
    except Bsr2IntegrationError as exc:
        raise PackageAuthorizationError(
            f"key slot for {identity_id!r} failed to authenticate: {exc}"
        ) from exc


def open_package(state: dict, identity_id: str, master_key: bytes, audit_dir=None) -> dict:
    """Open a package's payload as an authorized recipient.

    Returns ``(payload, updated_state)`` where ``updated_state`` has an
    ``"opened"`` entry appended to its custody chain. The caller is
    responsible for persisting ``updated_state`` if the custody record
    should be kept.
    """
    state = validate_package(state)
    try:
        content_key = _authorized_content_key(state, identity_id, master_key)
    except PackageAuthorizationError:
        if audit_dir is not None:
            audit.record_event(audit_dir, "open_denied", state["package_id"], identity_id)
        raise

    payload = ciphers.open_payload(content_key, state["package_id"], state["payload"])

    label = state["recipients"][identity_id]["label"]
    updated_state = dict(state)
    updated_state["custody_chain"] = custody.append(
        state["custody_chain"], "opened", label, {"identity_id": identity_id}
    )

    if audit_dir is not None:
        audit.record_event(audit_dir, "opened", state["package_id"], label)

    return payload, updated_state


def list_recipients(state: dict) -> list:
    """List every recipient's non-secret descriptor (id and label only)."""
    state = validate_package(state)
    return sorted(
        (
            {"identity_id": identity_id, "label": recipient["label"]}
            for identity_id, recipient in state["recipients"].items()
        ),
        key=lambda item: item["identity_id"],
    )


def custody_summary(state: dict) -> list:
    """A compact, display-friendly summary of the package's custody history."""
    return custody.summarize(state["custody_chain"])


def recipient_key_from_text(state: dict, identity_id: str, text: str) -> bytes:
    """Return the master key typed ``text`` gives ``identity_id``.

    The current text key when it verifies or when nothing verifies (so the
    caller's normal authorization error reports the mismatch), the legacy
    text key when only that one verifies.
    """
    current = ciphers.text_master_key(text)
    recipient = state["recipients"].get(identity_id)
    if recipient is None or verify_recipient_master_key(current, identity_id, recipient["verifier"]):
        return current
    legacy = ciphers.legacy_text_master_key(text)
    if verify_recipient_master_key(legacy, identity_id, recipient["verifier"]):
        return legacy
    return current


def needs_encryption_migration(state: dict, identity_id: str, text: str) -> bool:
    """Report whether ``identity_id``'s part of the package (its key, slot, or
    verifier) or the shared payload still uses the previous encryption."""
    state = validate_package(state)
    if identity_id not in state["recipients"]:
        return False
    return (
        recipient_key_from_text(state, identity_id, text) != ciphers.text_master_key(text)
        or is_legacy(state["key_slots"][identity_id])
        or is_legacy_binding(state["recipients"][identity_id]["verifier"])
        or is_legacy(state["payload"])
    )


def migrate_recipient(state: dict, identity_id: str, text: str, audit_dir=None) -> dict:
    """Move ``identity_id``'s slot and verifier, and the payload, to the
    current encryption. Raises PackageAuthorizationError when ``text`` does
    not authenticate ``identity_id``."""
    state = validate_package(state)
    old_key = recipient_key_from_text(state, identity_id, text)
    new_key = ciphers.text_master_key(text)
    content_key = _authorized_content_key(state, identity_id, old_key)
    package_id = state["package_id"]

    updated = dict(state)
    updated["payload"] = reseal(
        content_key, state["payload"], package_context(package_id),
        new_generator("package-migrate"),
    )
    updated["key_slots"] = dict(state["key_slots"])
    updated["key_slots"][identity_id] = ciphers.wrap_content_key(new_key, package_id, identity_id, content_key)
    updated["recipients"] = dict(state["recipients"])
    updated["recipients"][identity_id] = {
        **state["recipients"][identity_id],
        "verifier": build_recipient_verifier(new_key, identity_id),
    }
    label = state["recipients"][identity_id]["label"]
    updated["custody_chain"] = custody.append(
        state["custody_chain"], "payload_rewrapped", label,
        {"identity_id": identity_id, "reason": "encryption_migration"},
    )
    if audit_dir is not None:
        audit.record_event(audit_dir, "encryption_migrated", package_id, label)
    return updated
