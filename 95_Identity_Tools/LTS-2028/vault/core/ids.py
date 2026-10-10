"""
File: vault/core/ids.py

Purpose
-------
Record id generation and validation for the vault.

Communication / relationships
-----------------------------
Direct module imports: secrets.

Settings / parameters
---------------------
Module-level named settings: MAX_RECORD_ID_LENGTH, RECORD_ID_TOKEN_BYTES. See their definitions below for values.

Edge cases
----------
Additional edge-case guarantees are not established by this header; existing implementation and tests remain unchanged.

Known limitations
-----------------
This header update does not establish complete behavioral, platform, or security validation.

Examples
--------
Inspect the definitions below and the project documentation for supported usage.

Additional module documentation
-------------------------------
Record id generation and validation for the vault.

Unlike biometrics identity ids (which become filesystem path segments and so
must reject path separators), a vault record id is only ever used as a JSON
object key inside a single vault file. That is a narrower attack surface, but
the id still ends up embedded in the BSR2 context string
(:func:`crypto.context.record_context`), which rejects the ``|`` separator
and NUL bytes itself. Validation here catches those problems earlier, with a
message that names the actual field, rather than surfacing a generic context
error from deep inside the sealing call.
"""

import secrets

MAX_RECORD_ID_LENGTH = 128
RECORD_ID_TOKEN_BYTES = 16


class RecordIdError(ValueError):
    """Raised when a record id fails validation."""


def new_record_id() -> str:
    """Generate a fresh, random record id.

    Hex-encoded so it is always a valid record id under :func:`validate_record_id`
    without further checking.
    """
    return secrets.token_hex(RECORD_ID_TOKEN_BYTES)


def validate_record_id(record_id) -> str:
    """Validate a record id, returning it unchanged on success.

    Rejects empty strings, leading/trailing whitespace, excessive length, and
    the characters that would be rejected later by the BSR2 context builder
    anyway (``|`` and NUL) -- surfaced here as a record-id-specific error
    instead of a deeper context error.
    """
    if not isinstance(record_id, str) or not record_id:
        raise RecordIdError("record_id must be a non-empty string.")
    if record_id.strip() != record_id:
        raise RecordIdError("record_id cannot have leading or trailing whitespace.")
    if len(record_id) > MAX_RECORD_ID_LENGTH:
        raise RecordIdError(
            f"record_id cannot be longer than {MAX_RECORD_ID_LENGTH} characters."
        )
    if "|" in record_id:
        raise RecordIdError("record_id cannot contain '|'.")
    if "\x00" in record_id:
        raise RecordIdError("record_id cannot contain a NUL byte.")
    return record_id

