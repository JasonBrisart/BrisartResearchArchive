"""
File: tests/test_gui.py

Purpose
-------
Verify the desktop window's behavior without a display: every control exists, Build runs on
  the worker and shows the right dialogs, Recent Exports refreshes (proving the GUI records
  history), Performance and Recent Exports live on the Extras tab, the View tab hides and
  restores sections in place and remembers the choice without changing any setting, the
  layout reflows and a scrollbar exists only while a tab's content is taller than its
  window, the Extras tab disappears (now and at the next launch) when every one of its
  sections is hidden, hiding a section gives its space back on every tab (in real Tk a frame
  whose last child is removed keeps its old height, and the stand-in's layout model copies that
  rule, so these tests measure the holder frames instead of recomputing heights), the About tab
  has no update controls, hidden settings survive builds and profile
  saves, profiles round-trip, closing
  mid-build cancels and cleans up, profile save failures show an error instead of crashing,
  and the CPU Cores selector on simulated 1-, 4-, and 64-core machines. Also verifies that every
  export setting has a control (the Advanced Filters text boxes edit, validate, survive hiding,
  and are remembered), that size fields round-trip every byte count, and that a custom profile
  saves and restores everything: all settings, Open Export Folder After Build, the View choices,
  and (optionally) the project folder, skipping a missing folder with a note and leaving the
  window alone for a profile saved without a window half. Also verifies
  JobRunner results, errors, and refusing overlapping jobs.

Communication / relationships
-----------------------------
Imports tests/support.py (APP_ROOT). Each GUI scenario runs in a fresh Python process with
  tests/fake_tk.py installed as tkinter, then imports the real gui/ modules and builds each
  tab into its own frame, so inside(widget, frame) can tell which tab owns a control. JobRunner tests
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
    from application import storage
    import tkinter as tk
    import gui.state
    {cores_patch}
    from gui.state import make_gui_state, build_settings_from_state
    from gui.build_tab import create_build_tab
    from gui.options_tab import create_options_tab
    from gui.extras_tab import create_extras_tab
    from gui.view_tab import create_view_tab
    from gui.about_tab import create_about_tab
    window = tk.Tk()
    state = make_gui_state()
    build_frame, options_frame, extras_frame, view_frame, about_frame = (tk.Frame(window) for _ in range(5))
    create_build_tab(parent=build_frame, window=window, state=state)
    create_options_tab(parent=options_frame, state=state)
    create_extras_tab(parent=extras_frame, state=state)
    create_view_tab(parent=view_frame, state=state)
    create_about_tab(parent=about_frame)
    def inside(widget, frame):
        while widget is not None:
            if widget is frame:
                return True
            widget = widget.master
        return False
    def labelled(kind, text):
        return [w for w in fake_tk.REGISTRY if w.kind == kind and w.options.get('text') == text]
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

    def test_every_setting_comes_from_a_control_and_presets_restore_defaults(self):
        self.run_scenario('''
            from export.settings import settings_for_profile
            state.extensions_var.set('py, custom')
            state.exclude_dirs_var.set('tmp, scratch')
            state.exclude_files_var.set('notes.txt')
            state.exclude_suffixes_var.set('.png')
            state.require_complete_var.set(False)
            state.git_limit_var.set('9')
            state.workers_var.set('2 cores')
            settings = build_settings_from_state(state)
            assert settings.include_extensions == {'.py', '.custom'}, settings.include_extensions
            assert settings.exclude_dirs == {'tmp', 'scratch'} and settings.exclude_files == {'notes.txt'}
            assert settings.exclude_suffixes == {'.png'} and settings.require_complete_source is False
            assert settings.git_state_commit_limit == 9 and settings.workers == 2
            state.profile_var.set('standard')
            settings = build_settings_from_state(state)
            expected = settings_for_profile('standard')
            assert settings.include_extensions == expected.include_extensions
            assert settings.exclude_dirs == expected.exclude_dirs and '.env' in settings.exclude_files
            assert settings.exclude_suffixes == expected.exclude_suffixes
            assert settings.profile == 'standard' and settings.workers == 'auto', settings.workers
            assert settings == build_settings_from_state(state) and settings.git_state_commit_limit == 5
        ''', cores=4)

    def test_size_fields_round_trip_every_byte_count(self):
        self.run_scenario('''
            from gui.state import bytes_to_mb_text, parse_mb_to_bytes
            for n in list(range(1, 5000)) + [123456789, 2_000_000, 10 ** 10, 489, 251, 99_999_999_999]:
                assert parse_mb_to_bytes(bytes_to_mb_text(n), 'x') == n, n
            from application import storage
            from export.settings import settings_for_profile
            saved = settings_for_profile('archive')
            saved.max_file_bytes, saved.max_total_bytes = 489, 251_001
            storage.save_profile('Odd', saved)
            state.custom_profile_var.set('Odd')
            fake_tk.buttons('Load Selected')[0].invoke()
            assert build_settings_from_state(state).max_file_bytes == 489
            assert build_settings_from_state(state).max_total_bytes == 251_001
        ''')

    def test_advanced_filters_edit_validate_and_survive_hiding(self):
        self.run_scenario('''
            boxes = [w for w in fake_tk.REGISTRY if w.kind == 'Text' and inside(w, options_frame)]
            assert len(boxes) == 4, len(boxes)
            assert '.py' in boxes[0].content and '.env' in boxes[2].content and '.png' in boxes[3].content
            boxes[0].user_edit('py, MD\\ngo')
            assert build_settings_from_state(state).include_extensions == {'.py', '.md', '.go'}
            state.exclude_dirs_var.set('keep_out')
            assert boxes[1].content == 'keep_out', boxes[1].content
            section = labelled('LabelFrame', 'Advanced Filters')[0].master
            assert section.visible is True
            state.section_vars['options_advanced'].set(False)
            assert section.visible is False
            assert build_settings_from_state(state).exclude_dirs == {'keep_out'}
            state.section_vars['options_advanced'].set(True)
            assert section.visible is True
            for text, expected in ((' , ', 'cannot be empty'),):
                boxes[0].user_edit(text)
                try:
                    build_settings_from_state(state)
                except ValueError as exc:
                    assert expected in str(exc), exc
                else:
                    raise AssertionError('an empty extension list must be rejected')
            boxes[0].user_edit('py')
            state.custom_profile_var.set('Bad')
            for variable, text in ((state.exclude_dirs_var, 'a/b'), (state.exclude_files_var, 'c\\\\d'), (state.git_limit_var, 'many')):
                before = variable.get()
                variable.set(text)
                fake_tk.buttons('Save Current As')[0].invoke()
                assert fake_tk.MESSAGES[-1][:2] == ('showwarning', 'Invalid Settings'), fake_tk.MESSAGES[-1]
                variable.set(before)
            assert storage.list_profiles() == []
        ''')

    def test_last_used_settings_remember_the_advanced_filters(self):
        self.run_scenario('''
            state.selected_folder.set(str(project))
            state.extensions_var.set('py, custom')
            state.exclude_dirs_var.set('scratch')
            state.require_complete_var.set(False)
            build_button.invoke()
            window.run_pending()
            assert 'Build Complete' in [m[1] for m in fake_tk.MESSAGES], fake_tk.MESSAGES
            fresh = make_gui_state()
            restored = build_settings_from_state(fresh)
            assert restored.include_extensions == {'.py', '.custom'} and restored.exclude_dirs == {'scratch'}
            assert restored.require_complete_source is False
        ''')

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
            from gui.state import apply_settings_to_state
            wide = build_settings_from_state(state)
            wide.workers = 48
            apply_settings_to_state(state, wide)
            assert state.workers_var.get() == '32 cores'
        ''', cores=64)

    def test_single_core_machine(self):
        self.run_scenario('''
            combo = [w for w in fake_tk.REGISTRY if w.kind == 'Combobox' and w.options.get('textvariable') is state.workers_var][0]
            assert list(combo.options['values']) == ['Auto (1 core)', '1 core'], combo.options['values']
        ''', cores=1)

    def test_profile_saves_and_restores_everything_including_the_window(self):
        self.run_scenario('''
            import json
            state.custom_profile_var.set('Alice')
            state.selected_folder.set(str(project))
            state.extensions_var.set('py, bcc')
            state.exclude_dirs_var.set('build, tmp')
            state.exclude_files_var.set('.env, secret.txt')
            state.exclude_suffixes_var.set('.png, .zip')
            state.require_complete_var.set(False)
            state.git_limit_var.set('9')
            state.max_file_mb_var.set('0.000489')
            state.skipped_limit_var.set('7')
            state.include_zip_var.set(False)
            state.include_hashes_var.set(False)
            state.include_git_state_var.set(True)
            state.workers_var.set('2 cores')
            state.open_after_build_var.set(True)
            state.section_vars['extras_history'].set(False)
            state.section_vars['options_help'].set(False)
            before = build_settings_from_state(state)
            fake_tk.buttons('Save Current As')[0].invoke()
            entry = json.loads(storage.profiles_path().read_text(encoding='utf-8'))['profiles']['Alice']
            assert entry['window'] == {'open_after_build': True, 'hidden_sections': ['extras_history', 'options_help'],
                                       'project_folder': str(project)}, entry['window']
            assert entry['max_file_bytes'] == 489 and entry['workers'] == 2
            # the next person changes everything
            state.profile_var.set('standard')
            state.selected_folder.set('')
            state.open_after_build_var.set(False)
            for variable in state.section_vars.values():
                variable.set(True)
            state.extensions_var.set('txt')
            assert build_settings_from_state(state) != before
            fake_tk.buttons('Load Selected')[0].invoke()
            assert build_settings_from_state(state) == before
            assert state.selected_folder.get() == str(project) and state.open_after_build_var.get() is True
            hidden = sorted(key for key, variable in state.section_vars.items() if not variable.get())
            assert hidden == ['extras_history', 'options_help'], hidden
            assert storage.load_preferences().hidden_sections == ('extras_history', 'options_help') and storage.load_preferences().open_after_build
            assert fake_tk.MESSAGES[-1][:2] == ('showinfo', 'Profile Loaded'), fake_tk.MESSAGES[-1]
            fake_tk.buttons('Delete Selected')[0].invoke()
            assert storage.list_profiles() == []
        ''', cores=4)

    def test_profile_folder_is_optional_and_skipped_when_missing(self):
        self.run_scenario('''
            state.selected_folder.set(str(project))
            state.custom_profile_var.set('Shared')
            state.profile_folder_var.set(False)
            fake_tk.buttons('Save Current As')[0].invoke()
            assert storage.load_profile_window('Shared').project_folder == ''
            state.selected_folder.set('/keep/this')
            fake_tk.buttons('Load Selected')[0].invoke()
            assert state.selected_folder.get() == '/keep/this'
            from export.settings import settings_for_profile
            storage.save_profile('Elsewhere', settings_for_profile('archive'), window=storage.ProfileWindow(storage.AppPreferences(), '/no/such/folder'))
            state.custom_profile_var.set('Elsewhere')
            fake_tk.buttons('Load Selected')[0].invoke()
            assert state.selected_folder.get() == '/keep/this'
            assert 'was not found on this computer' in fake_tk.MESSAGES[-1][2] and '/no/such/folder' in fake_tk.MESSAGES[-1][2]
        ''')

    def test_profile_without_a_window_half_leaves_window_choices_alone(self):
        self.run_scenario('''
            from export.settings import settings_for_profile
            wanted = settings_for_profile('standard')
            wanted.exclude_dirs.add('from_cli')
            storage.save_profile('Cli', wanted)
            state.open_after_build_var.set(True)
            state.section_vars['extras_git'].set(False)
            state.custom_profile_var.set('Cli')
            fake_tk.buttons('Load Selected')[0].invoke()
            assert 'from_cli' in build_settings_from_state(state).exclude_dirs
            assert state.open_after_build_var.get() is True and state.section_vars['extras_git'].get() is False
            assert 'saved without window choices' in fake_tk.MESSAGES[-1][2], fake_tk.MESSAGES[-1]
        ''')

    def test_performance_and_recent_exports_live_on_extras(self):
        self.run_scenario('''
            combo = [w for w in fake_tk.REGISTRY if w.kind == 'Combobox' and w.options.get('textvariable') is state.workers_var][0]
            assert inside(combo, extras_frame) and not inside(combo, options_frame)
            tree = [w for w in fake_tk.REGISTRY if w.kind == 'Treeview'][0]
            assert inside(tree, extras_frame) and not inside(tree, about_frame)
            for title in ('Git State', 'Performance', 'Custom Profiles', 'Recent Exports'):
                assert all(inside(w, extras_frame) for w in labelled('LabelFrame', title)), title
            assert not any(inside(w, about_frame) for w in fake_tk.REGISTRY if w.kind in ('Treeview', 'Button'))
        ''')

    def test_view_tab_hides_restores_and_remembers_sections(self):
        self.run_scenario('''
            boxes = {w.options['text']: w.options['variable'] for w in fake_tk.REGISTRY if w.kind == 'Checkbutton' and inside(w, view_frame)}
            assert list(boxes) == ['Profile description', 'List of generated files', 'Option descriptions', 'Advanced filters',
                                   'Git State', 'Performance (CPU cores)', 'Custom Profiles', 'Recent Exports'], list(boxes)
            history = labelled('LabelFrame', 'Recent Exports')[0].master
            note = labelled('Label', 'Counts lines for included text files.')[0]
            assert history.visible and note.visible
            boxes['Recent Exports'].set(False)
            boxes['Option descriptions'].set(False)
            assert history.visible is False and note.visible is False
            saved = storage.load_preferences()
            assert sorted(saved.hidden_sections) == ['extras_history', 'options_help'], saved
            fresh = make_gui_state()
            assert not fresh.section_vars['extras_history'].get() and fresh.section_vars['extras_git'].get()
            boxes['Recent Exports'].set(True)
            assert history.visible is True
            titles = ('Git State', 'Performance', 'Custom Profiles', 'Recent Exports')
            sections = [labelled('LabelFrame', title)[0].master for title in titles]
            assert all(section.visible for section in sections)
            for key in ('Git State', 'Performance (CPU cores)', 'Custom Profiles', 'Recent Exports'):
                boxes[key].set(False)
            assert all(section.visible is False for section in sections), [s.visible for s in sections]
            assert not [w for w in fake_tk.REGISTRY if w.kind == 'Label' and 'Every Extras section is hidden' in (w.options.get('text') or '')]
            fake_tk.buttons('Show Everything')[0].invoke()
            assert all(var.get() for var in state.section_vars.values()) and all(section.visible for section in sections)
            assert storage.load_preferences().hidden_sections == ()
        ''')

    def test_scrollbar_appears_only_when_content_overflows(self):
        self.run_scenario('''
            from types import SimpleNamespace
            from gui.widgets import scrollbar_needed
            assert scrollbar_needed(800, 500) and not scrollbar_needed(500, 500) and not scrollbar_needed(300, 500)
            assert not scrollbar_needed(800, 1)
            canvas = [w for w in fake_tk.REGISTRY if w.kind == 'Canvas' and inside(w, options_frame)][0]
            bar = [w for w in fake_tk.REGISTRY if w.kind == 'Scrollbar' and inside(w, options_frame)][0]
            content = [c for c in canvas.calls if c[0] == 'create_window'][0][2]['window']
            assert bar.visible is None
            def settle(view, wanted):
                canvas.dimensions.update(height=view, width=700)
                content.dimensions['reqheight'] = wanted
                content.fire('<Configure>')
            def wheel_steps():
                canvas.fire('<Enter>')
                handler = [c for c in canvas.calls if c[0] == 'bind_all' and c[1][0] == '<MouseWheel>'][-1][1][1]
                before = len([c for c in canvas.calls if c[0] == 'yview_scroll'])
                handler(SimpleNamespace(delta=-120))
                return len([c for c in canvas.calls if c[0] == 'yview_scroll']) - before
            settle(600, 900)
            assert bar.visible is True and canvas.options['scrollregion'] == (0, 0, 700, 900)
            assert wheel_steps() == 1
            settle(600, 400)
            assert bar.visible is False and canvas.options['scrollregion'] == (0, 0, 700, 600)
            assert ('yview_moveto', (0,), {}) in canvas.calls
            assert wheel_steps() == 0
            settle(600, 900)
            assert bar.visible is True
            settle(600, 600)
            assert bar.visible is False
            canvas.fire('<Configure>', width=640, height=600)
            assert ('itemconfig', (1,), {'width': 640}) in canvas.calls
            extras_canvas = [w for w in fake_tk.REGISTRY if w.kind == 'Canvas' and inside(w, extras_frame)][0]
            extras_bar = [w for w in fake_tk.REGISTRY if w.kind == 'Scrollbar' and inside(w, extras_frame)][0]
            extras_content = [c for c in extras_canvas.calls if c[0] == 'create_window'][0][2]['window']
            extras_content.dimensions['reqheight'] = 5000
            extras_canvas.fire('<Map>')
            assert extras_bar.visible is None, 'a tab Tk has not sized yet must not show a scrollbar'
            extras_canvas.dimensions.update(height=500, width=700)
            extras_canvas.fire('<Map>')
            assert extras_bar.visible is True
        ''')

    def test_hiding_a_section_gives_back_its_space_on_every_tab(self):
        self.run_scenario('''
            def extras_content():
                canvas = [w for w in fake_tk.REGISTRY if w.kind == 'Canvas' and inside(w, extras_frame)][0]
                return [c for c in canvas.calls if c[0] == 'create_window'][0][2]['window']
            def options_content():
                canvas = [w for w in fake_tk.REGISTRY if w.kind == 'Canvas' and inside(w, options_frame)][0]
                return [c for c in canvas.calls if c[0] == 'create_window'][0][2]['window']
            outputs_label = [w for w in fake_tk.REGISTRY if w.kind == 'Label' and (w.options.get('text') or '').startswith('Generated outputs')][0]
            cases = [
                ('build_outputs', outputs_label.master, build_frame),
                ('options_advanced', labelled('LabelFrame', 'Advanced Filters')[0].master, options_content()),
                ('extras_git', labelled('LabelFrame', 'Git State')[0].master, extras_content()),
                ('extras_performance', labelled('LabelFrame', 'Performance')[0].master, extras_content()),
                ('extras_profiles', labelled('LabelFrame', 'Custom Profiles')[0].master, extras_content()),
                ('extras_history', labelled('LabelFrame', 'Recent Exports')[0].master, extras_content()),
            ]
            quick = labelled('LabelFrame', 'Quick Export')[0]
            description = [w for w in fake_tk.REGISTRY if w.kind == 'Label' and inside(w, quick) and w.options.get('wraplength') == 700][0]
            with_text = quick.requested_height()
            state.section_vars['build_profile_help'].set(False)
            assert quick.requested_height() < with_text and description.visible is False, 'the profile description left its space behind'
            state.section_vars['build_profile_help'].set(True)
            assert quick.requested_height() == with_text
            for key, section, tab in cases:
                holder = section.master
                shown_tab, shown_section = tab.winfo_reqheight(), section.requested_height()
                assert shown_section >= 20, (key, shown_section)
                state.section_vars[key].set(False)
                gap = holder.requested_height()
                assert gap <= 2, f'{key}: an empty {gap}px gap is left where the section was'
                assert shown_tab - tab.winfo_reqheight() >= shown_section, (key, shown_tab, tab.winfo_reqheight(), shown_section)
                state.section_vars[key].set(True)
                assert tab.winfo_reqheight() == shown_tab, (key, 'showing it again must restore the layout exactly')
                assert section.visible is True
        ''')

    def test_hiding_every_section_of_a_tab_collapses_it_and_its_scrollbar(self):
        self.run_scenario('''
            canvas = [w for w in fake_tk.REGISTRY if w.kind == 'Canvas' and inside(w, extras_frame)][0]
            bar = [w for w in fake_tk.REGISTRY if w.kind == 'Scrollbar' and inside(w, extras_frame)][0]
            content = [c for c in canvas.calls if c[0] == 'create_window'][0][2]['window']
            keys = ('extras_git', 'extras_performance', 'extras_profiles', 'extras_history')
            full = content.winfo_reqheight()
            state.section_vars['extras_history'].set(False)
            without_history = content.winfo_reqheight()
            assert without_history < full, f'hiding Recent Exports left the Extras content {full}px tall: no space was given back'
            state.section_vars['extras_history'].set(True)
            canvas.dimensions.update(height=(full + without_history) // 2, width=700)
            content.fire('<Configure>')
            assert bar.visible is True, 'all four sections are taller than the window'
            state.section_vars['extras_history'].set(False)
            content.fire('<Configure>')
            assert bar.visible is False, 'content now fits, so the scrollbar must go'
            for key in keys:
                state.section_vars[key].set(False)
            content.fire('<Configure>')
            intro = content.winfo_reqheight()
            assert intro < without_history / 2, (intro, without_history)
            assert canvas.options['scrollregion'][3] == canvas.winfo_height()
            for key in keys:
                state.section_vars[key].set(True)
            content.fire('<Configure>')
            assert content.winfo_reqheight() == full and bar.visible is True
        ''')

    def test_extras_tab_disappears_when_every_section_is_hidden(self):
        self.run_scenario('''
            import gui.window as main_gui
            from gui.state import SECTIONS
            fake_tk.REGISTRY.clear()
            keys = [key for key, tab, _label in SECTIONS if tab == 'Extras']
            def scenario(self):
                st = self._state
                notebook = [w for w in fake_tk.REGISTRY if w.kind == 'Notebook'][0]
                extras = [c[1][0] for c in notebook.calls if c[0] == 'add' and c[2].get('text') == 'Extras'][0]
                order = [c[2].get('text') for c in notebook.calls if c[0] == 'add']
                assert order == ['Build', 'Options', 'Extras', 'View', 'About'], order
                def tab_state():
                    return [c for c in notebook.calls if c[0] == 'tab' and c[1][0] is extras][-1][2]['state']
                assert tab_state() == 'normal'
                for key in keys[:-1]:
                    st.section_vars[key].set(False)
                    assert tab_state() == 'normal', key
                st.section_vars[keys[-1]].set(False)
                assert tab_state() == 'hidden'
                st.section_vars[keys[1]].set(True)
                assert tab_state() == 'normal'
                st.section_vars[keys[1]].set(False)
                assert tab_state() == 'hidden'
                view_button = [w for w in fake_tk.REGISTRY if w.kind == 'Button' and w.options.get('text') == 'Show Everything'][0]
                view_button.invoke()
                assert tab_state() == 'normal'
                self.destroy()
            fake_tk.Tk.mainloop = scenario
            real_make = main_gui.make_gui_state
            def capture():
                st = real_make()
                fake_tk.ROOT[-1]._state = st
                return st
            main_gui.make_gui_state = capture
            main_gui.run_gui()
        ''')

    def test_extras_tab_stays_hidden_at_next_launch(self):
        self.run_scenario('''
            import gui.window as main_gui
            from gui.state import SECTIONS
            keys = tuple(key for key, tab, _label in SECTIONS if tab == 'Extras')
            storage.save_preferences(storage.AppPreferences(hidden_sections=keys))
            fake_tk.REGISTRY.clear()
            def scenario(self):
                notebook = [w for w in fake_tk.REGISTRY if w.kind == 'Notebook'][0]
                extras = [c[1][0] for c in notebook.calls if c[0] == 'add' and c[2].get('text') == 'Extras'][0]
                states = [c[2]['state'] for c in notebook.calls if c[0] == 'tab' and c[1][0] is extras]
                assert states == ['hidden'], states
                self.destroy()
            fake_tk.Tk.mainloop = scenario
            main_gui.run_gui()
        ''')

    def test_hiding_a_section_keeps_its_setting(self):
        self.run_scenario('''
            state.include_git_state_var.set(True)
            state.section_vars['extras_git'].set(False)
            state.workers_var.set('2 cores')
            state.section_vars['extras_performance'].set(False)
            settings = build_settings_from_state(state)
            assert settings.include_git_state is True and settings.workers == 2
        ''', cores=4)

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
            with mock.patch('application.storage.save_profile', side_effect=TimeoutError('busy')):
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
