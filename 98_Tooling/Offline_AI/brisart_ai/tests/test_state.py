r"""
File: brisart_ai/tests/test_state.py

Purpose
-------
Verify path selection and legacy data migration with isolated files and
child processes.

Communication / relationships
-----------------------------
Direct module imports: contextlib, json, os, shutil, sqlite3, subprocess,
sys, tempfile, time, unittest, pathlib, brisart_ai.native_path, brisart_ai.state and
brisart_ai.knowledge.index (to build a real legacy index). Everything runs in
temporary directories with an explicit environment, so no test reads or
writes the real per-user folder. The end-to-end tests run a copy of cli.py
in a child process with HOME, APPDATA and XDG_CONFIG_HOME pointed at a
temporary folder. The child receives the external native API directory.

Settings / parameters
---------------------
- _legacy_project(root, rows) builds a project folder holding an old-style
  index with `rows` sources and a data/research_settings.json.
- _clean_env(home) is a child-process environment with every per-user
  location redirected and BRISARTAI_STATE_DIR removed.

Edge cases
----------
- A write-ahead log: rows that were never checkpointed into the main file
  must survive the move.
- A target settings file, or an index with content, that already exists is
  never overwritten; an index with no rows in any table is.
- A corrupt index is left in place with a warning, and no temporary file is
  left behind.
- Four processes released together move each file exactly once.

Known limitations
-----------------
- Windows file locking is not exercised: on Windows a legacy index held open
  by another process makes the move fail and keep the original, which these
  tests do not reproduce.
- The path of the real roaming profile is checked only as a string built from
  a supplied APPDATA value.

Examples
--------
python scripts/run_tests.py brisart_ai/tests/test_state.py
"""

import contextlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from brisart_ai import native_path, state
from brisart_ai.knowledge.index import Index

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _legacy_project(root: Path, rows: int = 2) -> Path:
    project = root / "project"
    (project / "data").mkdir(parents=True)
    with contextlib.closing(Index(str(project / state.INDEX_FILENAME))) as index:
        for number in range(rows):
            index.add_source("file", f"/doc{number}.txt", f"Doc {number}", f"unique zebra text {number}")
    (project / "data" / state.SETTINGS_FILENAME).write_text(
        '{"auto_web_research": true, "search_local_files": true, "search_notes": false}',
        encoding="utf-8",
    )
    return project


def _count_sources(path: Path) -> int:
    with contextlib.closing(sqlite3.connect(str(path))) as connection:
        return connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0]


def _clean_env(home: Path) -> dict:
    env = {key: value for key, value in os.environ.items() if key != state.STATE_DIR_ENV}
    for key in ("HOME", "USERPROFILE", "APPDATA", "XDG_CONFIG_HOME"):
        env[key] = str(home)
    return env


class TestStateDir(unittest.TestCase):
    def test_windows_uses_appdata(self):
        appdata = "C:\\Users\\me\\AppData\\Roaming"
        result = state.state_dir({"APPDATA": appdata}, platform="win32", home=Path("/h"))
        self.assertEqual(result, Path(appdata) / "Brisart Research Archive" / "BrisartAI")

    def test_windows_without_appdata_falls_back_to_roaming_under_home(self):
        result = state.state_dir({}, platform="win32", home=Path("/h"))
        self.assertEqual(result, Path("/h") / "AppData" / "Roaming" / "Brisart Research Archive" / "BrisartAI")

    def test_macos_uses_application_support(self):
        result = state.state_dir({}, platform="darwin", home=Path("/Users/me"))
        self.assertEqual(
            result,
            Path("/Users/me/Library/Application Support/Brisart Research Archive/BrisartAI"),
        )

    def test_linux_uses_xdg_config_home_then_dot_config(self):
        with_xdg = state.state_dir({"XDG_CONFIG_HOME": "/x"}, platform="linux", home=Path("/h"))
        without = state.state_dir({}, platform="linux", home=Path("/h"))
        self.assertEqual(with_xdg, Path("/x/Brisart Research Archive/BrisartAI"))
        self.assertEqual(without, Path("/h/.config/Brisart Research Archive/BrisartAI"))

    def test_override_replaces_the_whole_path(self):
        result = state.state_dir({state.STATE_DIR_ENV: "/usb/brisart", "APPDATA": "/ignored"}, platform="win32")
        self.assertEqual(result, Path("/usb/brisart"))

    def test_default_is_not_inside_the_project(self):
        self.assertNotIn(PROJECT_ROOT, state.state_dir().parents)
        self.assertEqual(state.index_path().name, state.INDEX_FILENAME)
        self.assertEqual(state.settings_path().name, state.SETTINGS_FILENAME)


class TestMigration(unittest.TestCase):
    def _run(self, project, target, env=None, log=None):
        messages = [] if log is None else log
        moved = state.migrate_legacy_state(project, environ=env or {}, target=target, log=messages.append)
        return moved, messages

    def test_moves_index_and_settings_and_removes_the_originals(self):
        with tempfile.TemporaryDirectory() as d:
            project = _legacy_project(Path(d), rows=3)
            settings_bytes = (project / "data" / state.SETTINGS_FILENAME).read_bytes()
            target = Path(d) / "state"
            moved, messages = self._run(project, target)
            self.assertEqual(moved, [state.INDEX_FILENAME, state.SETTINGS_FILENAME])
            self.assertEqual(_count_sources(target / state.INDEX_FILENAME), 3)
            self.assertEqual((target / state.SETTINGS_FILENAME).read_bytes(), settings_bytes)
            self.assertFalse((project / state.INDEX_FILENAME).exists())
            self.assertFalse((project / "data").exists())
            self.assertEqual(len(messages), 1)
            self.assertIn("Moved saved state", messages[0])
            self.assertEqual([p.name for p in target.iterdir() if p.name.startswith(".")], [])

    def test_second_run_does_nothing_and_says_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            project = _legacy_project(Path(d))
            target = Path(d) / "state"
            self._run(project, target)
            moved, messages = self._run(project, target)
            self.assertEqual((moved, messages), ([], []))

    def test_nothing_to_move_does_not_create_the_target_folder(self):
        with tempfile.TemporaryDirectory() as d:
            project = Path(d) / "project"
            project.mkdir()
            target = Path(d) / "state"
            moved, _ = self._run(project, target)
            self.assertEqual(moved, [])
            self.assertFalse(target.exists())

    def test_override_environment_variable_disables_the_move(self):
        with tempfile.TemporaryDirectory() as d:
            project = _legacy_project(Path(d))
            target = Path(d) / "state"
            moved, messages = self._run(project, target, env={state.STATE_DIR_ENV: str(target)})
            self.assertEqual((moved, messages), ([], []))
            self.assertTrue((project / state.INDEX_FILENAME).exists())
            self.assertFalse(target.exists())

    def test_rows_still_in_the_write_ahead_log_survive(self):
        with tempfile.TemporaryDirectory() as d:
            live = Path(d) / "live.sqlite3"
            connection = sqlite3.connect(str(live))
            try:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA wal_autocheckpoint=0")
                connection.execute("CREATE TABLE sources (id INTEGER PRIMARY KEY, text TEXT)")
                connection.commit()
                connection.execute("INSERT INTO sources(text) VALUES ('only in the wal')")
                connection.commit()
                project = Path(d) / "project"
                project.mkdir()
                for suffix in ("", "-wal", "-shm"):
                    shutil.copy2(str(live) + suffix, project / (state.INDEX_FILENAME + suffix))
            finally:
                connection.close()
            self.assertGreater((project / (state.INDEX_FILENAME + "-wal")).stat().st_size, 0)
            target = Path(d) / "state"
            moved, _ = self._run(project, target)
            self.assertEqual(moved, [state.INDEX_FILENAME])
            self.assertEqual(_count_sources(target / state.INDEX_FILENAME), 1)
            self.assertEqual(
                [p.name for p in project.iterdir() if p.name.startswith(state.INDEX_FILENAME)], []
            )

    def test_never_overwrites_a_file_already_in_the_target(self):
        with tempfile.TemporaryDirectory() as d:
            project = _legacy_project(Path(d), rows=5)
            target = Path(d) / "state"
            target.mkdir()
            (target / state.SETTINGS_FILENAME).write_text('{"search_notes": true}', encoding="utf-8")
            moved, _ = self._run(project, target)
            self.assertEqual(moved, [state.INDEX_FILENAME])
            self.assertEqual(
                (target / state.SETTINGS_FILENAME).read_text(encoding="utf-8"), '{"search_notes": true}'
            )
            self.assertTrue((project / "data" / state.SETTINGS_FILENAME).exists())

    def test_an_empty_index_left_by_a_failed_start_is_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            project = _legacy_project(Path(d), rows=3)
            target = Path(d) / "state"
            target.mkdir()
            Index(str(target / state.INDEX_FILENAME)).close()
            moved, _ = self._run(project, target)
            self.assertEqual(moved, [state.INDEX_FILENAME, state.SETTINGS_FILENAME])
            self.assertEqual(_count_sources(target / state.INDEX_FILENAME), 3)

    def test_an_index_with_content_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            project = _legacy_project(Path(d), rows=3)
            target = Path(d) / "state"
            target.mkdir()
            with contextlib.closing(Index(str(target / state.INDEX_FILENAME))) as index:
                index.add_source("file", "/new.txt", "New", "added after the failed move")
            moved, _ = self._run(project, target)
            self.assertEqual(moved, [state.SETTINGS_FILENAME])
            self.assertEqual(_count_sources(target / state.INDEX_FILENAME), 1)
            self.assertTrue((project / state.INDEX_FILENAME).exists())

    def test_corrupt_index_is_left_in_place_with_a_warning(self):
        with tempfile.TemporaryDirectory() as d:
            project = Path(d) / "project"
            project.mkdir()
            (project / state.INDEX_FILENAME).write_bytes(b"this is not a database" * 200)
            target = Path(d) / "state"
            moved, messages = self._run(project, target)
            self.assertEqual(moved, [])
            self.assertTrue((project / state.INDEX_FILENAME).exists())
            self.assertFalse((target / state.INDEX_FILENAME).exists())
            self.assertEqual([p.name for p in target.iterdir()], [])
            self.assertTrue(any("left where it is" in message for message in messages))

    def test_unwritable_target_keeps_everything_and_warns(self):
        with tempfile.TemporaryDirectory() as d:
            project = _legacy_project(Path(d))
            blocker = Path(d) / "not-a-folder"
            blocker.write_text("x", encoding="utf-8")
            moved, messages = self._run(project, blocker / "state")
            self.assertEqual(moved, [])
            self.assertTrue((project / state.INDEX_FILENAME).exists())
            self.assertEqual(len(messages), 1)

    def test_abandoned_lock_is_cleared(self):
        with tempfile.TemporaryDirectory() as d:
            project = _legacy_project(Path(d))
            target = Path(d) / "state"
            target.mkdir()
            lock = target / state.LOCK_FILENAME
            lock.write_text("", encoding="utf-8")
            old = time.time() - state.LOCK_STALE_SECONDS - 5
            os.utime(lock, (old, old))
            moved, _ = self._run(project, target)
            self.assertEqual(moved, [state.INDEX_FILENAME, state.SETTINGS_FILENAME])
            self.assertFalse(lock.exists())

    def test_four_processes_started_together_move_each_file_once(self):
        with tempfile.TemporaryDirectory() as d:
            project = _legacy_project(Path(d), rows=4)
            target = Path(d) / "state"
            go = Path(d) / "go"
            code = (
                "import json, sys, time\n"
                "from pathlib import Path\n"
                f"sys.path.insert(0, {str(PROJECT_ROOT)!r})\n"
                "from brisart_ai import state\n"
                f"go = Path({str(go)!r})\n"
                "while not go.exists():\n"
                "    time.sleep(0.005)\n"
                "moved = state.migrate_legacy_state("
                f"Path({str(project)!r}), environ={{}}, target=Path({str(target)!r}), log=lambda m: None)\n"
                "print(json.dumps(moved))\n"
            )
            children = [
                subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                for _ in range(4)
            ]
            go.write_text("", encoding="utf-8")
            reported = []
            for child in children:
                out, err = child.communicate(timeout=120)
                self.assertEqual(child.returncode, 0, msg=err)
                reported.extend(json.loads(out))
            self.assertEqual(sorted(reported), sorted([state.INDEX_FILENAME, state.SETTINGS_FILENAME]))
            self.assertEqual(_count_sources(target / state.INDEX_FILENAME), 4)
            self.assertFalse((target / state.LOCK_FILENAME).exists())


class TestEndToEnd(unittest.TestCase):
    def _copy_program(self, destination: Path) -> Path:
        program = destination / "program"
        program.mkdir()
        for name in ("cli.py", "run.py", "version.py"):
            shutil.copy2(PROJECT_ROOT / name, program / name)
        shutil.copytree(PROJECT_ROOT / "brisart_ai", program / "brisart_ai", ignore=shutil.ignore_patterns("__pycache__"))
        return program

    def test_cli_moves_old_state_once_and_leaves_the_program_folder_clean(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            program = self._copy_program(root)
            legacy = _legacy_project(root, rows=2)
            shutil.move(str(legacy / state.INDEX_FILENAME), str(program / state.INDEX_FILENAME))
            (program / "data").mkdir()
            shutil.move(str(legacy / "data" / state.SETTINGS_FILENAME), str(program / "data" / state.SETTINGS_FILENAME))
            home = root / "home"
            home.mkdir()
            env = _clean_env(home)
            env[native_path.ENV_VAR] = str(native_path.find_native_dir())
            expected = state.state_dir(env)

            def run_cli(*arguments):
                return subprocess.run(
                    [sys.executable, str(program / "cli.py"), *arguments],
                    cwd=str(program), env=env, capture_output=True, text=True, timeout=120,
                )

            first = run_cli("counts")
            self.assertEqual(first.returncode, 0, msg=first.stderr)
            self.assertIn("Sources: 2", first.stdout)
            self.assertIn("Moved saved state", first.stderr)
            self.assertTrue((expected / state.INDEX_FILENAME).exists())
            self.assertTrue((expected / state.SETTINGS_FILENAME).exists())
            second = run_cli("counts")
            self.assertEqual(second.returncode, 0, msg=second.stderr)
            self.assertEqual(second.stderr, "")
            self.assertEqual(
                sorted(p.name for p in program.iterdir() if p.name != "__pycache__"),
                ["brisart_ai", "cli.py", "run.py", "version.py"],
            )

    def test_fresh_install_creates_the_state_folder_and_nothing_beside_the_program(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            program = self._copy_program(root)
            home = root / "home"
            home.mkdir()
            env = _clean_env(home)
            env[native_path.ENV_VAR] = str(native_path.find_native_dir())
            result = subprocess.run(
                [sys.executable, str(program / "cli.py"), "note", "Title", "body text about zebras"],
                cwd=str(program), env=env, capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(result.stderr, "")
            expected = state.state_dir(env)
            self.assertTrue((expected / state.INDEX_FILENAME).exists())
            self.assertTrue((expected / state.SETTINGS_FILENAME).exists())
            self.assertEqual(
                sorted(p.name for p in program.iterdir() if p.name != "__pycache__"),
                ["brisart_ai", "cli.py", "run.py", "version.py"],
            )


if __name__ == "__main__":
    unittest.main()
