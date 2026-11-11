"""
File: entitle/__init__.py

Purpose
-------
Hold the four things every part of Entitle shares and that belong to no single domain: the
  EntitleError base class, canonical JSON (the exact bytes that are sealed and hashed), the UTC
  clock, and the check that a required text field is not blank. Keeping them at the package
  root means the record log never has to import the entitlement rules just to raise an error
  or hash a record.

Communication / relationships
-----------------------------
Imports only the standard library (datetime, json). Imported, as `from entitle import ...`, by
  entitle/rights.py (EntitleError, utc_now), entitle/encryption.py (EntitleError),
  entitle/entitlements.py (EntitleError, canonical_json, require_text, utc_now_iso),
  entitle/records.py (EntitleError, canonical_json, utc_now_iso), entitle/revoke.py and
  entitle/tracking.py (require_text), cli.py and gui/window.py (EntitleError), and
  examples/protected_app_example.py (EntitleError). Importing any entitle module runs this file
  first; it does no I/O.

Settings / parameters
---------------------
canonical_json(data) returns UTF-8 bytes with sorted keys, no spaces and non-ASCII kept as
  written. Those bytes are what an entitlement payload is sealed as and what every record's
  entry_hash covers, so changing the encoding would break every existing record chain.
  utc_now() returns an aware UTC datetime; utc_now_iso() the same at second resolution as ISO
  text (for example "2026-11-10T22:56:00+00:00"). require_text(**fields) takes keyword
  arguments named after the fields, so the error names the field the operator typed.

Edge cases
----------
require_text raises ValueError (not EntitleError) for the first value that is not a string,
  is empty, or is only whitespace; the message turns underscores into spaces, for example
  "fork name is required.". Values are not stripped, so " lab-a " passes and is stored as typed.
  canonical_json raises TypeError for values JSON cannot represent; Entitle only passes it
  dictionaries of text, numbers, booleans and None.

Known limitations
-----------------
utc_now reads the local clock, so expiry and record timestamps are only as right as that clock.
  require_text checks presence, not format: an ID with unusual characters is accepted.

Examples
--------
From the directory containing main.py:

    from entitle import EntitleError, canonical_json, require_text

    assert canonical_json({"b": 1, "a": "é"}) == '{"a":"é","b":1}'.encode("utf-8")
    try:
        require_text(product="Demo", fork_name="  ")
    except ValueError as exc:
        assert str(exc) == "fork name is required."
    assert issubclass(EntitleError, Exception)
"""

import datetime
import json


class EntitleError(Exception):
    """Base class for every error Entitle raises on purpose."""


def canonical_json(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def utc_now_iso():
    return utc_now().replace(microsecond=0).isoformat()


def require_text(**fields):
    for name, value in fields.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name.replace('_', ' ')} is required.")
