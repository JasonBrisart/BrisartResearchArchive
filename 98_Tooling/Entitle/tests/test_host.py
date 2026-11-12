"""
File: tests/test_host.py

Purpose
-------
Verify entitle/host.py: the machine fingerprint is well formed and stable, and HostState notices a
  clock wound backwards and a revocation list older than one already seen, without ever moving
  its own memory backwards, and refuses to silently reset when its file is damaged.

Communication / relationships
-----------------------------
Imports entitle/host.py and entitle/common.py (EntitleError). Needs no encryption. Run by
  pytest; nothing imports it.

Settings / parameters
---------------------
Times are fixed datetimes in UTC, so the tests do not depend on the machine's clock. State files
  are written under pytest's tmp_path.

Edge cases
----------
Covers a first run (no file), a clock inside and outside the tolerance, an equal and an older
  revocation sequence, separate sequences per signing key, a damaged state file, and a state
  file that must exist but does not.

Known limitations
-----------------
The fingerprint is checked on the machine running the tests only; the Windows registry branch
  is not exercised on Linux.

Examples
--------
From the directory containing run.py:

    python -m pytest tests/test_host.py
"""
import datetime

import pytest

from entitle.common import EntitleError
from entitle.host import HostState, is_fingerprint, machine_fingerprint

T0 = datetime.datetime(2027, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)


def _at(minutes):
    return T0 + datetime.timedelta(minutes=minutes)


class TestFingerprint:
    def test_it_is_well_formed_and_stable(self):
        first = machine_fingerprint()
        assert is_fingerprint(first) and first == machine_fingerprint()

    @pytest.mark.parametrize("text", ["", "m1:", "m1:" + "g" * 32, "m2:" + "0" * 32, "m1:" + "0" * 31, None, 7])
    def test_anything_else_is_not_a_fingerprint(self, text):
        assert not is_fingerprint(text)


class TestClock:
    def test_the_clock_only_ever_moves_forward_in_memory(self, tmp_path):
        state = HostState(tmp_path / "state.json")
        assert state.check_clock(_at(0)) is None and state.latest_time() == _at(0)
        assert state.check_clock(_at(60)) is None and state.latest_time() == _at(60)
        assert state.check_clock(_at(58)) is None and state.latest_time() == _at(60)  # within 5 minutes

    def test_a_clock_wound_back_past_the_tolerance_is_reported(self, tmp_path):
        state = HostState(tmp_path / "state.json")
        state.check_clock(_at(60))
        assert state.check_clock(_at(54)) == "clock_rollback_detected"
        assert HostState(tmp_path / "state.json", tolerance_seconds=3600).check_clock(_at(1)) is None


class TestRevocationSequence:
    def test_an_older_list_from_the_same_key_is_refused(self, tmp_path):
        state = HostState(tmp_path / "state.json")
        assert state.check_revocation_sequence("key-a", 4) is None
        assert state.check_revocation_sequence("key-a", 4) is None
        assert state.check_revocation_sequence("key-a", 3) == "revocation_list_rollback"
        assert state.check_revocation_sequence("key-b", 1) is None
        assert state.check_revocation_sequence("key-a", 9) is None
        assert state.check_revocation_sequence("key-a", 5) == "revocation_list_rollback"


class TestStateFile:
    @pytest.mark.parametrize("content", ["not json", "[]", '{"format": "other"}', '{"format": "entitle.host-state.v1"}'])
    def test_a_damaged_state_file_is_an_error_not_a_silent_reset(self, tmp_path, content):
        path = tmp_path / "state.json"
        path.write_text(content, encoding="utf-8")
        with pytest.raises(EntitleError, match="host state file\\) is damaged"):
            HostState(path).check_clock(_at(0))
        assert path.read_text(encoding="utf-8") == content

    def test_a_state_file_that_must_exist_is_reported_missing(self, tmp_path):
        with pytest.raises(EntitleError, match="is missing"):
            HostState(tmp_path / "state.json", require_existing=True).check_clock(_at(0))
