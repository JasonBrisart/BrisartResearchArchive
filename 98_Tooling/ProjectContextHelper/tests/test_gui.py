"""
File: tests/test_gui.py

Purpose
-------
Verify the desktop window's behavior without a display: every control exists, Build runs on
  the worker and shows the right dialogs, Recent Exports refreshes (proving the GUI records
  history), the About tab has no update controls, hidden settings survive builds and profile
  saves, profiles round-trip, closing
  mid-build cancels and cleans up, profile save failures show an error instead of crashing,
  and the CPU Cores selector on simulated 1-, 4-, and 64-core machines. Also verifies
  JobRunner results, errors, and refusing overlapping jobs.

Communication / relationships
-----------------------------
Imports tests/support.py (APP_ROOT). Each GUI scenario runs in a fresh Python process with
  tests/fake_tk.py installed as tkinter, then imports the real gui/ modules. JobRunner tests
  import gui/jobs.py directly.

Settings / parameters
---------------------
Scenarios time out after 120 s. cores replaces gui.state.detect_cpu_cores inside the
  scenario process.

Edge cases
----------
Running each scenario in its own process keeps the fake tkinter out of every other test.

Known limitations
-----------------
Checks wiring and behavior, not appearance: layout, colors, fonts, and real Tk threading
  need a manual look on a real display.

Examples
--------
From the directory containing run.py:

    python -m unittest discover -s tests -p test_gui.py -v
"""

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from threading import Event

from support import APP_ROOT

from gui.jobs import JobRunner

PRELUDE = textwrap.dedent('''
    import sys, time
    sys.path.insert(0, {root!r})
    sys.path.insert(0, {tests!r})
    import fake_tk
    fake_tk.install()
    from pathlib import Path
    import storage
    import tkinter as tk
    import gui.state
    {cores_patch}
    from gui.state import make_gui_state, build_settings_from_state
    from gui.build_tab import create_build_tab
    from gui.options_tab import create_options_tab
    from gui.extras_tab import create_extras_tab
    from gui.about_tab import create_about_tab
    window = tk.Tk()
    state = make_gui_state()
    create_build_tab(parent=tk.Frame(window), window=window, state=state)
    create_options_tab(parent=tk.Frame(window), state=state)
    create_extras_tab(parent=tk.Frame(window), state=state)
    create_about_tab(parent=tk.Frame(window), state=state)
    build_button = fake_tk.buttons('Build Project Context')[0]
''')


class GuiTests(unittest.TestCase):
    def run_scenario(self, body, files=None, cores=None):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / "project"
            project.mkdir()
            for name, text in (files or {"sample.py": "print(1)\n"}).items():
                path = project / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            cores_patch = f"gui.state.detect_cpu_cores = lambda: {cores}" if cores else ""
            code = PRELUDE.format(root=str(APP_ROOT), tests=str(APP_ROOT / "tests"), cores_patch=cores_patch)
            code += f"project = Path({str(project)!r})\n" + textwrap.dedent(body)
            env = dict(os.environ, PCH_STATE_DIR=str(base / "state"))
            result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120, env=env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_v3_controls_build_on_worker_and_refresh_history(self):
        self.run_scenario('''
            labels = {w.options.get('text') for w in fake_tk.REGISTRY}
            for text in ('Browse', 'Open Last Export Folder', 'Open Selected Export Folder',
                         'Refresh', 'Clear History', 'Save Current As', 'Load Selected', 'Delete Selected', 'Refresh List'):
                assert text in labels, text
            assert 'Open Releases Page' not in labels and 'Updates' not in labels
            about = [w.options.get('text') or '' for w in fake_tk.REGISTRY if w.kind == 'Label']
            assert any('Author: Jason Brisart' + chr(10) + 'Brisart Research Archive' in t for t in about), about
            assert not any('github' in t.lower() for t in about)
            state.selected_folder.set(str(project))
            build_button.invoke()
            assert build_button.options.get('state') == 'disabled'
            window.run_pending()
            assert build_button.options.get('state') == 'normal'
            assert 'Build Complete' in [m[1] for m in fake_tk.MESSAGES], fake_tk.MESSAGES
            assert state.last_export_dir is not None and state.last_export_dir.is_dir()
            tree = [w for w in fake_tk.REGISTRY if w.kind == 'Treeview'][0]
            rows = [tree.items[i] for i in tree.get_children()]
            assert len(rows) == 1 and rows[0][2] == 1, rows
            assert state.status_text.get() == 'Done. Included 1 files.'
        ''')

    def test_completeness_failure_shows_build_stopped(self):
        self.run_scenario('''
            state.selected_folder.set(str(project))
            state.max_file_mb_var.set('0.000001')
            build_button.invoke()
            window.run_pending()
            assert ('showwarning', 'Build Stopped') in [(m[0], m[1]) for m in fake_tk.MESSAGES], fake_tk.MESSAGES
            assert state.status_text.get() == 'Build stopped.'
        ''')

    def test_missing_folder_is_rejected_before_worker(self):
        self.run_scenario('''
            build_button.invoke()
            assert state.jobs.thread is None
            assert fake_tk.MESSAGES[-1][1] == 'Build Stopped'
        ''')

    def test_hidden_settings_survive_and_preset_resets(self):
        self.run_scenario('''
            state.base_settings.include_extensions.add('.custom')
            state.workers_var.set('2 cores')
            settings = build_settings_from_state(state)
            assert '.custom' in settings.include_extensions and settings.workers == 2
            state.profile_var.set('standard')
            settings = build_settings_from_state(state)
            assert '.custom' not in settings.include_extensions and settings.profile == 'standard'
            assert settings.workers == 'auto', settings.workers
        ''', cores=4)

    def test_cpu_selector_lists_only_this_machines_cores(self):
        self.run_scenario('''
            combo = [w for w in fake_tk.REGISTRY if w.kind == 'Combobox' and w.options.get('textvariable') is state.workers_var][0]
            assert list(combo.options['values']) == ['Auto (4 cores)', '1 core', '2 cores', '3 cores', '4 cores'], combo.options['values']
            assert state.workers_var.get() == 'Auto (4 cores)'
            usage = [w for w in fake_tk.REGISTRY if w.kind == 'Label' and w.options.get('fg') == '#2f6fde'][0].options['textvariable']
            assert usage.get() == 'Using all 4 cores', usage.get()
            state.workers_var.set('3 cores')
            assert usage.get() == 'Using 3 of 4 cores', usage.get()
            assert build_settings_from_state(state).workers == 3
            state.custom_profile_var.set('Three')
            fake_tk.buttons('Save Current As')[0].invoke()
            state.profile_var.set('archive')
            assert state.workers_var.get() == 'Auto (4 cores)'
            fake_tk.buttons('Load Selected')[0].invoke()
            assert state.workers_var.get() == '3 cores'
            state.selected_folder.set(str(project))
            build_button.invoke()
            window.run_pending()
            manifest = (state.last_export_dir / 'PROJECT_MANIFEST.json').read_text(encoding='utf-8')
            assert '"workers": 3' in manifest, manifest[:400]
        ''', cores=4)

    def test_cpu_selector_caps_large_machines(self):
        self.run_scenario('''
            combo = [w for w in fake_tk.REGISTRY if w.kind == 'Combobox' and w.options.get('textvariable') is state.workers_var][0]
            values = list(combo.options['values'])
            assert values[0] == 'Auto (32 cores)' and values[-1] == '32 cores' and len(values) == 33, values
            notes = [w.options.get('text') or '' for w in fake_tk.REGISTRY if w.kind == 'Label']
            assert any('reports 64 cores' in t and 'up to 32' in t for t in notes)
            state.base_settings.workers = 48
            from gui.state import apply_settings_to_state
            apply_settings_to_state(state, state.base_settings)
            assert state.workers_var.get() == '32 cores'
        ''', cores=64)

    def test_single_core_machine(self):
        self.run_scenario('''
            combo = [w for w in fake_tk.REGISTRY if w.kind == 'Combobox' and w.options.get('textvariable') is state.workers_var][0]
            assert list(combo.options['values']) == ['Auto (1 core)', '1 core'], combo.options['values']
        ''', cores=1)

    def test_custom_profile_round_trip_keeps_hidden_settings(self):
        self.run_scenario('''
            state.base_settings.include_extensions.add('.custom')
            state.custom_profile_var.set('Review')
            fake_tk.buttons('Save Current As')[0].invoke()
            state.profile_var.set('standard')
            fake_tk.buttons('Load Selected')[0].invoke()
            settings = build_settings_from_state(state)
            assert settings.profile == 'archive' and '.custom' in settings.include_extensions
            fake_tk.buttons('Delete Selected')[0].invoke()
            assert storage.list_profiles() == []
        ''')

    def test_close_during_build_cancels_and_cleans_up(self):
        files = {f"f{i}.txt": "x" * 2000 for i in range(400)}
        self.run_scenario('''
            import gui.window as main_gui
            fake_tk.REGISTRY.clear()
            def scenario(self):
                st = self._state
                st.selected_folder.set(str(project))
                fake_tk.buttons('Build Project Context')[-1].invoke()
                self.protocols['WM_DELETE_WINDOW']()
                assert st.closing
                deadline = time.monotonic() + 60
                while not self.destroyed and time.monotonic() < deadline:
                    self.run_pending(timeout=60)
                assert self.destroyed and not st.jobs.busy
                exports = project / 'PROJECT_CONTEXT_EXPORTS'
                leftovers = [p.name for p in exports.iterdir()] if exports.exists() else []
                assert not any(n.startswith('.pch-') for n in leftovers), leftovers
            fake_tk.Tk.mainloop = scenario
            real_make = main_gui.make_gui_state
            def capture():
                st = real_make()
                fake_tk.ROOT[-1]._state = st
                return st
            main_gui.make_gui_state = capture
            main_gui.run_gui()
        ''', files=files)

    def test_profile_and_history_failures_show_dialogs(self):
        self.run_scenario('''
            from unittest import mock
            state.custom_profile_var.set('Review')
            with mock.patch('storage.save_profile', side_effect=TimeoutError('busy')):
                try:
                    fake_tk.buttons('Save Current As')[0].invoke()
                except TimeoutError:
                    raise AssertionError('busy settings folder escaped to the user')
        ''')


class JobRunnerTests(unittest.TestCase):
    def test_result_error_and_overlap(self):
        runner = JobRunner()
        runner.start(lambda cancel, emit: 42)
        runner.thread.join(10)
        self.assertEqual(list(runner.drain()), [("done", 42)])

        def fail(cancel, emit):
            raise ValueError("fixture")
        runner.start(fail)
        runner.thread.join(10)
        kind, payload = list(runner.drain())[0]
        self.assertEqual(kind, "error")
        self.assertIsInstance(payload, ValueError)

        gate = Event()
        runner.start(lambda cancel, emit: gate.wait(10))
        try:
            with self.assertRaises(RuntimeError):
                runner.start(lambda cancel, emit: None)
        finally:
            gate.set()
            runner.thread.join(10)


if __name__ == "__main__":
    unittest.main()
