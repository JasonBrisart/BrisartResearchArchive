"""
File: tests/test_gui_wiring.py

Purpose
-------
Exercise the unchanged v3.1.4 desktop interface on top of the v4.0.0 engine without a display,
  using the recording tkinter stand-in in tests/fake_tk.py.

Implemented responsibilities:
- run_scenario: Run one scenario in a fresh subprocess with fake tkinter installed, a temporary
  project, and PCH_STATE_DIR pointing at a temporary state folder.
- test_*: Check that every v3.1.4 control is built, that Build runs on the worker and shows the
  original dialogs, that Recent Exports refreshes, that hidden settings survive, that profiles
  round-trip through the Extras controls, and that closing mid-build cancels and cleans up.

Communication / relationships
-----------------------------
Internal imports and exchanged symbols (inside the scenario subprocesses):
- gui.builders: make_gui_state, build_settings_from_state.
- gui.build_tab / gui.options_tab / gui.extras_tab / gui.about_tab: create_* tab functions.
- gui.main_gui: run_gui.
- services: storage.

Consumers in the supplied source:
No application module imports this file; it is run by unittest discovery.

Settings / parameters
---------------------
Each scenario has a 120 second subprocess timeout.

Function signatures (nested callbacks are scoped to their enclosing function):
- run_scenario(self, body: str, files: dict[str, str] | None=None) -> None

Edge cases
----------
Subprocess isolation keeps fake tkinter out of every other test module.

Known limitations
-----------------
Verifies wiring and control flow only, not rendering, layout, fonts, real Tk threading rules, or
  platform dialogs. A manual check on a real display is still required.

Examples
--------
Usage from the directory containing run.py:

    python -m unittest discover -s tests -p test_gui_wiring.py -v
"""

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]

PRELUDE = textwrap.dedent('''
    import sys, time
    sys.path.insert(0, {root!r})
    sys.path.insert(0, {tests!r})
    import fake_tk
    fake_tk.install()
    from pathlib import Path
    from services import storage
    import tkinter as tk
    from gui.builders import make_gui_state, build_settings_from_state
    from gui.build_tab import create_build_tab
    from gui.options_tab import create_options_tab
    from gui.extras_tab import create_extras_tab
    from gui.about_tab import create_about_tab
    window = tk.Tk()
    state = make_gui_state()
    create_build_tab(parent=tk.Frame(window), window=window, state=state)
    create_options_tab(parent=tk.Frame(window), state=state)
    create_extras_tab(parent=tk.Frame(window), state=state)
    create_about_tab(parent=tk.Frame(window), window=window, state=state)
    build_button = fake_tk.buttons('Build Project Context')[0]
''')


class GuiWiringTests(unittest.TestCase):
    def run_scenario(self, body, files=None):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / "project"
            project.mkdir()
            for name, text in (files or {"sample.py": "print(1)\n"}).items():
                path = project / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            code = PRELUDE.format(root=str(APP_ROOT), tests=str(APP_ROOT / "tests"))
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
            assert 'Open Releases Page' not in labels
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
            state.base_settings.workers = 2
            settings = build_settings_from_state(state)
            assert '.custom' in settings.include_extensions and settings.workers == 2
            state.profile_var.set('standard')
            settings = build_settings_from_state(state)
            assert '.custom' not in settings.include_extensions and settings.profile == 'standard'
        ''')

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
            import gui.main_gui as main_gui
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


if __name__ == "__main__":
    unittest.main()
