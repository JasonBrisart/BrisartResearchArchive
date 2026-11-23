"""
File: crypto/context.py

Purpose
-------
Canonical context strings that bind every sealed object to what it is.

Public interface:
- record_context(record_id, kind, label)
- template_context(identity_id, modality)
- attachment_context(identity_id, filename)
- identity_context(identity_id)
- package_context(package_id)
- key_slot_context(package_id, identity_id)
- keyring_context(wrapper)

Design notes:

This module is the single source of the context strings passed to BSR2's
authenticated envelope (crypto.envelope) and factor layer (crypto.factors). A
biometric template sealed for one identity/modality cannot be dropped into
another's slot, a vault record's payload cannot be swapped with a different
record's, and a package key slot cannot be moved between recipients or packages
-- in every case the moved envelope fails authentication instead of decrypting
into the wrong place (see docs/BSR2_INTEGRATION.md's "Context binding"
section).

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.errors (crypto/errors.py)
Standard library: none.
Imported by:
- biometrics/engine/attachments.py
- biometrics/engine/enrollment.py
- biometrics/engine/verification.py
- crypto/keyring.py
- packages/ciphers.py
- vault/store/vault_service.py
Covered by tests: crypto/tests/test_context.py.

Settings / parameters
---------------------
- SEPARATOR = "|"
- _PREFIX = "BrisartIdentityTools/v1"

Edge cases
----------
- _clean() raises Bsr2IntegrationError: "context {...} must be a string."
- _clean() raises Bsr2IntegrationError: "context {...} cannot be empty."
- _clean() raises Bsr2IntegrationError: "context {...} cannot contain {...}."
- _clean() raises Bsr2IntegrationError: "context {...} cannot contain a NUL
  byte."

Known limitations
-----------------
- A context is authenticated alongside the ciphertext, so an envelope sealed
  under one context cannot be opened under another: this is the mechanism that
  makes cross-substitution detectable across the whole ecosystem.
- Security rests on BSR2, a custom research construction that has not been
  independently audited (see docs/SECURITY.md); do not treat it as a
  replacement for vetted, audited cryptography.

Examples
--------
Call shapes only, not a runnable script: record_id, kind, label, identity_id,
modality, filename stand for values the caller supplies.

::

    from crypto.context import (
        record_context,
        template_context,
        attachment_context,
    )
    record_context(record_id, kind, label)
    template_context(identity_id, modality)
    attachment_context(identity_id, filename)
"""

from crypto.errors import Bsr2IntegrationError

SEPARATOR = "|"
_PREFIX = "BrisartIdentityTools/v1"

def _clean(name, value):
    if not isinstance(value, str):
        raise Bsr2IntegrationError(f"context {name} must be a string.")
    if not value:
        raise Bsr2IntegrationError(f"context {name} cannot be empty.")
    if SEPARATOR in value:
        raise Bsr2IntegrationError(f"context {name} cannot contain {SEPARATOR!r}.")
    if "\x00" in value:
        raise Bsr2IntegrationError(f"context {name} cannot contain a NUL byte.")
    return value
def _join(kind, *parts):
    return SEPARATOR.join((_PREFIX, kind, *parts))
def record_context(record_id, kind, label):
    return _join("vault-record", _clean("record_id", record_id), _clean("kind", kind), _clean("label", label))
def template_context(identity_id, modality):
    return _join("biometrics-template", _clean("identity_id", identity_id), _clean("modality", modality))
def attachment_context(identity_id, filename):
    # Distinct "kind" prefix from template_context ("biometrics-attachment"
    # vs "biometrics-template"), and the filename is bound alongside the
    # identity_id, so a sealed attachment can never be swapped onto a
    # different identity OR relabeled as a different attachment name
    # without failing authentication -- the same cross-substitution
    # protection template_context already gives modality templates.
    return _join("biometrics-attachment", _clean("identity_id", identity_id), _clean("filename", filename))
def identity_context(identity_id):
    return _join("biometrics-identity", _clean("identity_id", identity_id))
def package_context(package_id):
    return _join("ibp-package", _clean("package_id", package_id))
def key_slot_context(package_id, identity_id):
    return _join("ibp-key-slot", _clean("package_id", package_id), _clean("identity_id", identity_id))
def keyring_context(wrapper):
    return _join("keyring-wrapper", _clean("wrapper", wrapper))




