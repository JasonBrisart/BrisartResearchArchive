"""
File: entitle/host.py

Purpose
-------
Own the facts about the machine a protected program runs on that an offline check can use: a
  machine fingerprint (for entitlements bound to particular machines) and a small state file
  that remembers the latest time and the newest revocation list this machine has seen, so a
  clock wound backwards or an old revocation list put back is noticed. Neither needs a network.

Communication / relationships
-----------------------------
Imports entitle/common.py (EntitleError, utc_now, write_text_atomically) and the standard
  library (hashlib, json, os, platform, uuid, and winreg on Windows). Imported by
  entitle/entitlements.py (machine_fingerprint, when an entitlement is bound to machines, and
  HostState), cli.py (fingerprint command, verify --state) and examples/protected_app_example.py.
  Covered by tests/test_host.py.

Settings / parameters
---------------------
machine_fingerprint() returns "m1:" and 32 hex characters: SHA-256 over the platform name and the
  operating system's machine identifier (/etc/machine-id or /var/lib/dbus/machine-id on Linux, the
  MachineGuid registry value on Windows; elsewhere, macOS included, the network hardware address
  from uuid.getnode() and the host name). It runs no other program. HostState(path,
  tolerance_seconds=300) keeps JSON {"format", "latest_time", "revocation_sequences": {issuer key
  ID: sequence}}.

Edge cases
----------
HostState.check_clock(now) returns "clock_rollback_detected" when now is earlier than the
  latest time seen minus the tolerance, and otherwise records now (only ever moving forward).
  check_revocation_sequence(key_id, sequence) returns "revocation_list_rollback" for a list
  older than one already seen from that key, and otherwise records it. A missing state file is
  a first run. A state file that cannot be read is an EntitleError, not a silent reset, because
  deleting or damaging it is exactly what someone winding the clock back would do; the operator
  decides whether to remove it. The file is written in one step.

Known limitations
-----------------
These are deterrents for honest-but-careless machines, not enforcement against a determined
  administrator: a fingerprint can be copied or spoofed by someone who controls the machine,
  and the state file can be deleted (which is reported only if the program insists the file
  exists; HostState(require_existing=True)). Changing the operating system installation changes
  the fingerprint; issue a new entitlement then. A machine whose identifier cannot be read uses
  the hardware address, which can change with network adapters.

Examples
--------
From the directory containing run.py:

    from tempfile import TemporaryDirectory
    from entitle.host import HostState, machine_fingerprint

    print(machine_fingerprint())
    with TemporaryDirectory() as folder:
        state = HostState(f"{folder}/entitle-host-state.json")
        assert state.check_clock() is None
"""
import datetime
import hashlib
import json
import os
import platform
import uuid
from pathlib import Path

from .common import EntitleError, utc_now, write_text_atomically

FINGERPRINT_PREFIX = "m1:"
STATE_FORMAT = "entitle.host-state.v1"
DEFAULT_TOLERANCE_SECONDS = 300


def _machine_identifier():
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                return "windows-machine-guid:" + str(winreg.QueryValueEx(key, "MachineGuid")[0]).lower()
        except OSError:
            pass
    for candidate in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            value = Path(candidate).read_text(encoding="ascii").strip()
        except (OSError, UnicodeDecodeError):
            continue
        if value:
            return "machine-id:" + value
    return f"hardware-address:{uuid.getnode():012x}:{platform.node().lower()}"


def machine_fingerprint():
    """A stable, non-secret identifier for this machine, for binding entitlements to it."""
    material = f"Entitle machine fingerprint v1\x00{platform.system()}\x00{_machine_identifier()}"
    return FINGERPRINT_PREFIX + hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def is_fingerprint(text):
    body = text[len(FINGERPRINT_PREFIX):] if isinstance(text, str) and text.startswith(FINGERPRINT_PREFIX) else ""
    return len(body) == 32 and all(character in "0123456789abcdef" for character in body)


class HostState:
    """What this machine has already seen: the latest time and the newest revocation lists."""

    def __init__(self, path, *, tolerance_seconds=DEFAULT_TOLERANCE_SECONDS, require_existing=False):
        self.path = Path(path)
        self.tolerance = datetime.timedelta(seconds=tolerance_seconds)
        self.require_existing = require_existing

    def _load(self):
        if not self.path.exists():
            if self.require_existing:
                raise EntitleError(f"{self.path.name} (the host state file) is missing; it may have been deleted.")
            return {"format": STATE_FORMAT, "latest_time": None, "revocation_sequences": {}}
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            state = None
        if (
            not isinstance(state, dict)
            or state.get("format") != STATE_FORMAT
            or not isinstance(state.get("revocation_sequences"), dict)
        ):
            raise EntitleError(f"{self.path.name} (the host state file) is damaged; remove it only if you trust this clock.")
        return state

    def _save(self, state):
        write_text_atomically(self.path, json.dumps(state, indent=2, sort_keys=True))

    def latest_time(self):
        value = self._load().get("latest_time")
        return datetime.datetime.fromisoformat(value) if value else None

    def check_clock(self, now=None):
        """None when the clock is plausible (and remember it), else "clock_rollback_detected"."""
        now = now or utc_now()
        state = self._load()
        latest = datetime.datetime.fromisoformat(state["latest_time"]) if state.get("latest_time") else None
        if latest and now < latest - self.tolerance:
            return "clock_rollback_detected"
        if latest is None or now > latest:
            state["latest_time"] = now.replace(microsecond=0).isoformat()
            self._save(state)
        return None

    def check_revocation_sequence(self, key_id, sequence):
        """None when this revocation list is not older than one already seen, else a reason."""
        state = self._load()
        seen = state["revocation_sequences"].get(key_id)
        if isinstance(seen, int) and sequence < seen:
            return "revocation_list_rollback"
        if seen is None or sequence > seen:
            state["revocation_sequences"][key_id] = sequence
            self._save(state)
        return None
