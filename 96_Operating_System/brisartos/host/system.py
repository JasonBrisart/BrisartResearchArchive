r"""
File: brisartos/host/system.py

Purpose
-------
Expose three host-backed values: command-line arguments, the current UTC
timestamp and a randomly generated hexadecimal identifier.

Public interface:
- command_line_arguments() -- Return sys.argv without the program name, as a
  list of text.
- now_utc() -- Return the current time as an ISO 8601 string with an explicit
  +00:00 offset.
- new_id() -- Return 32 lowercase hexadecimal characters (128 random bits from
  secrets.token_hex).

Design notes:

command_line_arguments slices sys.argv to omit the executable name. now_utc
uses an aware UTC datetime and isoformat(); new_id requests sixteen random
bytes as hexadecimal text. These wrappers return host results without caching,
validation or a fallback source.

Communication / relationships
-----------------------------
Standard library: datetime, secrets, sys.
Imported by:
- brisartos/kernel/kernel.py
- brisartos/modules/api.py
- brisartos/shell/commands.py
- brisartos/shell/console.py
Covered by tests: brisartos/host/tests/test_system.py.

Settings / parameters
---------------------
No module-level settings. The clock and entropy source are whatever the host
provides.

Edge cases
----------
None of these functions raises or catches anything of its own. Standard-library
exceptions would reach the caller, but none are expected in normal use.

Known limitations
-----------------
- The clock is whatever the host reports, so it can be wrong or move backwards.
  Timestamps are not trusted external time evidence.
- Identifiers are 128 random bits from the operating system's entropy source.
  This module does not add entropy or establish independent assurance about it.

Examples
--------
Run from the repository root.

::

    from brisartos.host import system

    assert system.now_utc().endswith('+00:00')
    assert len(system.new_id()) == 32
    assert isinstance(system.command_line_arguments(), list)
"""

import secrets
import sys
from datetime import datetime, timezone


def command_line_arguments():
    return sys.argv[1:]


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def new_id():
    return secrets.token_hex(16)
