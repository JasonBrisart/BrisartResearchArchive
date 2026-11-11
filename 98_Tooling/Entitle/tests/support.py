"""
File: tests/support.py

Purpose
-------
Hold what the test files share: the Entitle folder, the demo identity and key, the
  entitlement file written by the previous encryption, a helper that issues a real protected
  entitlement, a helper that holds a record store's writer lock from another process, and a
  helper that runs run.py as a real process.

Communication / relationships
-----------------------------
Imports entitle/entitlements.py (issue_entitlement) when issue_demo is called. Imported by
  tests/test_entitlements.py, tests/test_cli.py, tests/test_gui.py, tests/test_example.py,
  tests/test_records.py, tests/test_tracking.py, tests/test_report.py, tests/test_encryption.py
  and tests/test_end_to_end.py. conftest.py puts the Entitle folder on sys.path before any test
  imports this file.

Settings / parameters
---------------------
MASTER_KEY (45 characters) meets BSR2's 32-byte minimum; DRBG_SEED (64 characters) and
  DRBG_PERSONALIZATION meet the minimums of the optional generator and are used only by tests
  of that option. ISSUER, SUBJECT and PRODUCT are the demo identity used by the fixtures in
  tests/fixtures/. LEGACY_ENTITLEMENT is a BSR2 Alpha 3 envelope sealed, with the copy of BSR2
  that Entitle carried before 0.5.0, for that identity and key (entitlement lab-a-demo-001,
  modify and fork, limit 2).
  issue_demo(path, entitlement_id, **rights) takes the rights flags of issue_entitlement and
  uses no generator option. store_lock_held_elsewhere(store_path) is a context manager that
  keeps the lock held by a separate process (killed on exit, which is also how a crashed writer
  looks). run_entitle(*args, cwd, env) runs run.py and returns the finished process with text
  output.

Edge cases
----------
run_entitle starts a new Python process with a 120 second limit and runs it in cwd (default: the
  current folder), so tests can prove run.py works from a different working folder. env adds to
  the parent's environment. The demo key is a test value; it protects nothing.

Known limitations
-----------------
The helpers assume a working entitle/ package; a failure there shows up as a failure in every
  test that uses them.

Examples
--------
From a test file in tests/:

    from support import issue_demo

    def test_example(tmp_path):
        issue_demo(tmp_path / "demo.entitle", modify=True)
"""

import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

ENTITLE_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
LEGACY_ENTITLEMENT = FIXTURES / "legacy_alpha3_entitlement.json"

MASTER_KEY = "change-this-master-key-change-this-master-key"
DRBG_SEED = "a" * 64
DRBG_PERSONALIZATION = "EntitleTestPersonalization"
ISSUER = "JasonBrisart"
SUBJECT = "ResearchLabA"
PRODUCT = "EntitleDemo"


def issue_demo(path, entitlement_id="ent-1", **rights):
    from entitle.entitlements import issue_entitlement

    return issue_entitlement(
        issuer=ISSUER,
        subject=SUBJECT,
        product=PRODUCT,
        entitlement_id=entitlement_id,
        master_key=MASTER_KEY,
        output=path,
        **rights,
    )


@contextmanager
def store_lock_held_elsewhere(store_path):
    """Hold the store's writer lock in another process until the block ends, then kill it."""
    code = (
        "import sys, time; sys.path.insert(0, sys.argv[1]);"
        "from entitle.records import RecordStore;"
        "t = RecordStore(sys.argv[2]).transaction(); t.__enter__();"
        "print('held', flush=True); time.sleep(600)"
    )
    holder = subprocess.Popen(
        [sys.executable, "-c", code, str(ENTITLE_ROOT), str(store_path)], stdout=subprocess.PIPE, text=True
    )
    try:
        assert holder.stdout.readline().strip() == "held"
        yield holder
    finally:
        holder.kill()
        holder.wait(timeout=30)


def run_entitle(*args, cwd=None, env=None, root=None):
    """Run run.py (from `root`, default this Entitle folder) as a real process."""
    environment = {**os.environ, **(env or {})}
    return subprocess.run(
        [sys.executable, str((root or ENTITLE_ROOT) / "run.py"), *args],
        capture_output=True, text=True, timeout=120, cwd=cwd, env=environment,
    )
