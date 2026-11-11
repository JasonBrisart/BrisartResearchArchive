"""
File: tests/test_cli.py

Purpose
-------
Verify the command line end to end: the full lifecycle (issue, verify, governed deployments up
  to and past the limit, fork, provenance, list, revoke, refused deployment, reinstate, check,
  report, tamper detection), migrating a file from the previous encryption, every expected
  failure printing one clean error with the right exit status, usage errors, help and version
  (with the linked encryption), and that main.py works from another working folder without
  loading tkinter.

Communication / relationships
-----------------------------
Imports cli.py, version.py and entitle/records.py (to shorten the store lock wait), and runs
  main.py as a real process for the working-folder and tkinter checks. Uses tests/support.py
  (including the lock holder) and the fixtures in tests/fixtures/ (an entitlement written by the
  previous encryption and a record log written by v0.4.1).
  Run by pytest; nothing imports it.

Settings / parameters
---------------------
Most tests call cli.main(argv) in this process and read pytest's capsys; the process tests use
  support.run_main. Everything is written under pytest's tmp_path. The demo key is a test value.

Edge cases
----------
Covers: verify denied (exit 1, no migration note), a refused deployment (exit 0, "recorded":
  false), a damaged record store (report says BROKEN and exits 0; other commands print an error
  and exit 1), a store locked by another process, a short key or seed, an invalid expiry or
  deployment limit, a blank required field (nothing written), a missing file, a file migrate
  cannot open (left unchanged), an unknown command or record type (exit 2), no arguments (help,
  exit 0), a Python without tkinter, and a broken window module that must surface as itself
  rather than as a missing tkinter.

Known limitations
-----------------
Running without 97_Encryption is tested in tests/test_encryption.py. Does not open a real
  window (tests/test_gui.py uses a tkinter stand-in) and does not run on Windows or macOS from
  here, so path quoting in those shells is untested.

Examples
--------
From the directory containing main.py:

    python -m pytest tests/test_cli.py
"""

import json
import shutil
import subprocess
import sys

import pytest

import cli
from entitle import records
from support import (
    DRBG_PERSONALIZATION, DRBG_SEED, ENTITLE_ROOT, FIXTURES, ISSUER, LEGACY_ENTITLEMENT, MASTER_KEY, PRODUCT,
    SUBJECT, run_main, store_lock_held_elsewhere,
)
from version import __version__


def _call(capsys, *argv):
    code = cli.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _identity(*, with_subject=True):
    args = ["--issuer", ISSUER]
    if with_subject:
        args += ["--subject", SUBJECT]
    return args + ["--product", PRODUCT]


def _issue_args(path, entitlement_id="lab-1", *extra):
    return [
        "issue", *_identity(), "--entitlement-id", entitlement_id, "--master-key", MASTER_KEY,
        "--output", str(path), *extra,
    ]


def _deploy_args(path, store, host):
    return ["track", "deploy", *_identity(), "--master-key", MASTER_KEY, "--entitlement", str(path),
            "--host", host, "--store", str(store)]


class TestLifecycle:
    def test_the_whole_workflow_runs_and_the_audit_trail_verifies(self, tmp_path, capsys):
        entitlement, store = tmp_path / "ent" / "lab.entitle", tmp_path / "rec" / "r.log"

        code, out, _ = _call(capsys, *_issue_args(entitlement, "lab-1", "--deployment-limit", "5", "--modify", "--fork"))
        assert code == 0 and entitlement.is_file()
        assert out.startswith("Protected entitlement created:") and '"can_modify": true' in out

        code, out, _ = _call(capsys, "verify", *_identity(), "--master-key", MASTER_KEY, "--file", str(entitlement))
        assert code == 0 and "VERIFIED: entitlement is valid." in out

        code, out, _ = _call(capsys, "verify", *_identity(), "--master-key", "wrong-key-wrong-key-wrong-key-wrong-key",
                             "--file", str(entitlement))
        assert code == 1 and "DENIED: bsr_verification_failed" in out

        for host in ("node-1", "node-2"):
            code, out, _ = _call(capsys, *_deploy_args(entitlement, store, host))
            assert code == 0 and json.loads(out)["recorded"] is True

        code, out, _ = _call(capsys, "track", "fork", "--product", PRODUCT, "--source-version", "1.4.0",
                             "--fork-name", "lab-custom", "--maintainer", SUBJECT, "--store", str(store))
        assert code == 0 and json.loads(out)["record_type"] == "fork"
        code, out, _ = _call(capsys, "track", "provenance", "--product", PRODUCT, "--origin", ISSUER,
                             "--version", "1.4.0", "--previous-version", "1.3.0", "--custodian", SUBJECT, "--store", str(store))
        assert code == 0 and json.loads(out)["data"]["previous_version"] == "1.3.0"

        code, out, _ = _call(capsys, "track", "list", "--type", "fork", "--store", str(store))
        assert code == 0 and [r["record_type"] for r in json.loads(out)] == ["fork"]

        code, out, _ = _call(capsys, "revoke", "revoke", "--entitlement-id", "lab-1", "--reason", "key compromise", "--store", str(store))
        assert code == 0 and json.loads(out)["data"]["reason"] == "key compromise"
        code, out, _ = _call(capsys, "revoke", "check", "--entitlement-id", "lab-1", "--store", str(store))
        assert code == 0 and out.rstrip().endswith("REVOKED")

        code, out, _ = _call(capsys, *_deploy_args(entitlement, store, "node-3"))
        assert code == 0 and json.loads(out)["reason"] == "entitlement_revoked"

        code, out, _ = _call(capsys, "revoke", "reinstate", "--entitlement-id", "lab-1", "--reason", "cleared", "--store", str(store))
        assert code == 0
        code, out, _ = _call(capsys, "revoke", "check", "--entitlement-id", "lab-1", "--store", str(store))
        assert out.rstrip().endswith("ACTIVE")
        code, out, _ = _call(capsys, *_deploy_args(entitlement, store, "node-3"))
        assert json.loads(out)["deployments_used"] == 3

        code, out, _ = _call(capsys, "report", "--store", str(store))
        assert code == 0
        assert "deployment: 3" in out and "fork: 1" in out and "revocation: 1" in out and "reinstatement: 1" in out
        assert "EntitleDemo: 3" in out and "VERIFIED: hash chain intact across 7 records." in out

        report_file = tmp_path / "out" / "audit.json"
        code, out, _ = _call(capsys, "report", "--store", str(store), "--format", "json", "--output", str(report_file))
        assert code == 0 and out.strip() == f"Report written to {report_file}"
        assert json.loads(report_file.read_text(encoding="utf-8"))["chain"] == {
            "valid": True, "broken_index": None, "reason": "ok", "record_count": 7}

    def test_the_deployment_limit_refuses_with_exit_zero_and_a_reason(self, tmp_path, capsys):
        entitlement, store = tmp_path / "lab.entitle", tmp_path / "r.log"
        _call(capsys, *_issue_args(entitlement, "lab-1", "--deployment-limit", "1"))
        assert json.loads(_call(capsys, *_deploy_args(entitlement, store, "a"))[1])["recorded"] is True
        code, out, _ = _call(capsys, *_deploy_args(entitlement, store, "b"))
        outcome = json.loads(out)
        assert code == 0 and outcome["recorded"] is False
        assert (outcome["reason"], outcome["deployment_limit"], outcome["deployments_used"]) == ("deployment_limit_reached", 1, 1)

    def test_editing_a_record_is_reported_as_a_broken_chain(self, tmp_path, capsys):
        store = tmp_path / "r.log"
        for name in ("a", "b", "c"):
            _call(capsys, "track", "fork", "--product", PRODUCT, "--source-version", "1", "--fork-name", name,
                  "--maintainer", "m", "--store", str(store))
        lines = store.read_text(encoding="utf-8").strip().split("\n")
        record = json.loads(lines[1])
        record["data"]["fork_name"] = "edited"
        lines[1] = json.dumps(record, sort_keys=True)
        store.write_text("\n".join(lines) + "\n", encoding="utf-8")
        code, out, _ = _call(capsys, "report", "--store", str(store))
        assert code == 0 and "BROKEN: entry_hash_mismatch at record index 1." in out


class TestExpectedFailures:
    def test_a_short_key_is_one_clean_line_with_the_reason(self, tmp_path, capsys):
        args = _issue_args(tmp_path / "x.entitle")
        args[args.index(MASTER_KEY)] = "short"
        code, out, err = _call(capsys, *args)
        assert code == 1 and out == ""
        assert err.strip() == "Error: BSR2 encryption failed: master key must contain at least 32 bytes"
        assert not (tmp_path / "x.entitle").exists()

    def test_a_short_seed_is_one_clean_line_with_the_reason(self, tmp_path, capsys):
        code, _, err = _call(capsys, *_issue_args(tmp_path / "x.entitle", "lab-1", "--drbg-seed", "short"))
        assert code == 1 and "seed must contain at least 64 bytes" in err and "Traceback" not in err

    def test_the_generator_options_are_optional_and_accepted(self, tmp_path, capsys):
        path = tmp_path / "x.entitle"
        code, _, _ = _call(capsys, *_issue_args(path, "lab-1", "--drbg-seed", DRBG_SEED,
                                              "--drbg-personalization", DRBG_PERSONALIZATION))
        assert code == 0
        code, out, _ = _call(capsys, "verify", *_identity(), "--master-key", MASTER_KEY, "--file", str(path))
        assert code == 0 and "VERIFIED" in out

    def test_a_missing_entitlement_file_is_an_error_not_a_traceback(self, tmp_path, capsys):
        code, out, err = _call(capsys, "verify", *_identity(), "--master-key", MASTER_KEY, "--file", str(tmp_path / "nope.entitle"))
        assert code == 1 and out == "" and err.startswith("Error: ") and "nope.entitle" in err and "Traceback" not in err

    def test_a_damaged_store_stops_commands_with_an_error_naming_the_record(self, tmp_path, capsys):
        store = tmp_path / "r.log"
        store.write_text('{"not": "complete', encoding="utf-8")
        code, _, err = _call(capsys, "revoke", "check", "--entitlement-id", "x", "--store", str(store))
        assert code == 1 and "record 0 is not a valid JSON object" in err

    def test_a_busy_store_is_reported_not_hung(self, tmp_path, capsys, monkeypatch):
        store = tmp_path / "r.log"
        monkeypatch.setattr(records, "LOCK_TIMEOUT_SECONDS", 0.2)
        with store_lock_held_elsewhere(store):
            code, _, err = _call(capsys, "track", "fork", "--product", "P", "--source-version", "1", "--fork-name", "f",
                                 "--maintainer", "m", "--store", str(store))
        assert code == 1 and "record store is busy" in err

    def test_the_window_command_explains_a_missing_tkinter(self, capsys, monkeypatch):
        for name in [m for m in sys.modules if m == "gui" or m.startswith("gui.")]:
            monkeypatch.delitem(sys.modules, name)
        monkeypatch.setitem(sys.modules, "tkinter", None)
        code, _, err = _call(capsys, "gui")
        assert code == 1 and "needs tkinter" in err

    def test_a_broken_window_module_is_not_disguised_as_a_missing_tkinter(self, capsys, monkeypatch):
        monkeypatch.setitem(sys.modules, "gui.window", None)
        with pytest.raises(ModuleNotFoundError):
            cli.main(["gui"])

    @pytest.mark.parametrize("flag,value,message", [
        ("--expires", "next tuesday", "expires is not an ISO timestamp"),
        ("--deployment-limit", "-1", "deployment limit must be a whole number of 0 or more"),
        ("--entitlement-id", "  ", "entitlement id is required"),
    ])
    def test_an_entitlement_that_could_never_work_is_not_issued(self, tmp_path, capsys, flag, value, message):
        path = tmp_path / "x.entitle"
        args = _issue_args(path)
        if flag in args:
            args[args.index(flag) + 1] = value
        else:
            args += [flag, value]
        code, out, err = _call(capsys, *args)
        assert code == 1 and out == "" and message in err
        assert not path.exists()

    def test_a_blank_required_field_is_refused_before_the_permanent_log_is_touched(self, tmp_path, capsys):
        store = tmp_path / "r.log"
        code, _, err = _call(capsys, "track", "fork", "--product", PRODUCT, "--source-version", "1",
                             "--fork-name", "", "--maintainer", "m", "--store", str(store))
        assert code == 1 and err.strip() == "Error: fork name is required."
        code, _, err = _call(capsys, "revoke", "revoke", "--entitlement-id", " ", "--store", str(store))
        assert code == 1 and "entitlement id is required" in err
        assert not store.exists()

    def test_a_report_on_a_store_that_does_not_exist_succeeds_and_says_so(self, tmp_path, capsys):
        code, out, _ = _call(capsys, "report", "--store", str(tmp_path / "typo.log"))
        assert code == 0 and "this store file does not exist" in out


class TestUsage:
    def test_no_arguments_prints_help_with_every_command(self, capsys):
        code, out, _ = _call(capsys)
        assert code == 0
        for command in ("issue", "verify", "track", "revoke", "report", "gui"):
            assert command in out

    def test_version_flag_prints_the_version_file_value(self, capsys):
        with pytest.raises(SystemExit) as caught:
            cli.main(["--version"])
        assert caught.value.code == 0
        first, second = capsys.readouterr().out.strip().splitlines()
        assert first == f"Entitle {__version__}"
        assert second.startswith("Encryption: BSR2 Alpha") and second.endswith(", from 97_Encryption/Official")
        assert __version__.count(".") >= 2

    @pytest.mark.parametrize("argv", [
        ["bogus"],
        ["track", "list", "--type", "bogus", "--store", "x"],
        ["verify", "--issuer", "a"],
        ["revoke"],
    ])
    def test_usage_errors_exit_with_status_two(self, argv, capsys):
        with pytest.raises(SystemExit) as caught:
            cli.main(argv)
        assert caught.value.code == 2
        assert "usage:" in capsys.readouterr().err


class TestMigrate:
    def _legacy(self, tmp_path):
        path = tmp_path / "legacy.entitle"
        shutil.copyfile(LEGACY_ENTITLEMENT, path)
        return path

    def _migrate_args(self, path, key=MASTER_KEY):
        return ["migrate", *_identity(), "--master-key", key, "--file", str(path)]

    def test_verify_points_a_previous_format_file_at_migrate_and_migrate_fixes_it(self, tmp_path, capsys):
        path = self._legacy(tmp_path)
        code, out, _ = _call(capsys, "verify", *_identity(), "--master-key", MASTER_KEY, "--file", str(path))
        assert code == 0 and "VERIFIED: entitlement is valid." in out and cli.PREVIOUS_ENCRYPTION_NOTE in out
        code, out, err = _call(capsys, *self._migrate_args(path))
        assert code == 0 and err == ""
        assert out.splitlines()[0] == f"MIGRATED: {path} now uses the current encryption (BSR2-S64-SIV)."
        assert "Entitle versions before 0.5.0 cannot open it" in out
        code, out, _ = _call(capsys, "verify", *_identity(), "--master-key", MASTER_KEY, "--file", str(path))
        assert code == 0 and "VERIFIED" in out and "NOTE" not in out
        code, out, _ = _call(capsys, *self._migrate_args(path))
        assert code == 0 and out.strip() == f"UNCHANGED: {path} already uses the current encryption."

    def test_a_denied_file_gets_no_migration_note(self, tmp_path, capsys):
        path = self._legacy(tmp_path)
        code, out, _ = _call(capsys, "verify", *_identity(), "--master-key", "wrong-key-wrong-key-wrong-key-wrong-key",
                             "--file", str(path))
        assert code == 1 and "DENIED" in out and "NOTE" not in out

    def test_a_file_that_does_not_open_is_an_error_and_is_not_changed(self, tmp_path, capsys):
        path = self._legacy(tmp_path)
        before = path.read_bytes()
        code, out, err = _call(capsys, *self._migrate_args(path, key="wrong-key-wrong-key-wrong-key-wrong-key"))
        assert code == 1 and out == "" and "Nothing was changed." in err and "Traceback" not in err
        assert path.read_bytes() == before

    def test_migrating_a_missing_file_is_an_error(self, tmp_path, capsys):
        code, _, err = _call(capsys, *self._migrate_args(tmp_path / "nope.entitle"))
        assert code == 1 and err.startswith("Error: ") and "nope.entitle" in err


class TestFilesAndLogsWrittenByEarlierReleases:
    def test_the_previous_encryption_entitlement_verifies_through_the_command_line(self, capsys):
        code, out, _ = _call(capsys, "verify", *_identity(), "--master-key", MASTER_KEY, "--file", str(LEGACY_ENTITLEMENT))
        assert code == 0 and "VERIFIED" in out

    def test_the_previous_release_log_reports_as_verified(self, capsys):
        code, out, _ = _call(capsys, "report", "--store", str(FIXTURES / "legacy_v0_4_1_records.log"))
        assert code == 0 and "VERIFIED: hash chain intact across 6 records." in out

    def test_revocation_history_in_the_previous_release_log_reads_as_active(self, capsys):
        code, out, _ = _call(capsys, "revoke", "check", "--entitlement-id", "lab-a-demo-001",
                             "--store", str(FIXTURES / "legacy_v0_4_1_records.log"))
        assert out.rstrip().endswith("ACTIVE")


class TestRealProcess:
    def test_main_works_from_any_working_folder(self, tmp_path):
        elsewhere = tmp_path / "somewhere" / "else"
        elsewhere.mkdir(parents=True)
        version = run_main("--version", cwd=elsewhere)
        assert version.returncode == 0 and version.stdout.splitlines()[0] == f"Entitle {__version__}"
        issued = run_main(*_issue_args("lab.entitle"), cwd=elsewhere)
        assert issued.returncode == 0, issued.stderr
        verified = run_main("verify", *_identity(), "--master-key", MASTER_KEY, "--file", "lab.entitle", cwd=elsewhere)
        assert verified.returncode == 0 and "VERIFIED" in verified.stdout
        denied = run_main("verify", *_identity(), "--master-key", "wrong-key-wrong-key-wrong-key-wrong-key",
                          "--file", "lab.entitle", cwd=elsewhere)
        assert denied.returncode == 1

    def test_commands_other_than_gui_never_load_tkinter(self, tmp_path):
        code = (
            f"import sys; sys.path.insert(0, {str(ENTITLE_ROOT)!r}); import cli;"
            f"assert cli.main(['report', '--store', {str(tmp_path / 'r.log')!r}]) == 0;"
            "assert 'tkinter' not in sys.modules and 'gui' not in sys.modules"
        )
        assert subprocess.run([sys.executable, "-c", code], capture_output=True).returncode == 0
