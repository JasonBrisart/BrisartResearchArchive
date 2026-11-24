"""
File: tests/gui_doubles_check.py

Purpose
-------
Drive the GUI end to end with stand-in widget classes on machines without
Tk: the Archive window and every page, the TFL options screen, a complete
run answered only from the keyboard (including the five affect values on
the keys 1 to 5), the input guard that ignores answers right after a screen
is drawn, the hand-off to the Results page when a run finishes, the
held-key guard, Esc to stop a run, closing the Archive during a run, the
Results page's single and multi-session analysis, and the scrolling
helpers.

Communication / relationships
-----------------------------
- Run in its own interpreter by tests/test_tfl.py (IsolationTests), because
  it replaces tkinter in sys.modules.
- Imports gui/main_window.py (and through it every page and controller),
  gui/pages/results_page.py, frameworks/TFL/gui_session.py,
  frameworks/TFL/gui_options.py, frameworks/TFL/gui_screens.py, and
  frameworks/TFL/headless.py.

Settings / parameters
---------------------
- Widget: accepts any call and returns None (winfo_exists returns True,
  winfo_children returns []).
- Var: stores a value like a Tk variable.
- APP: a stand-in for the Archive window exposing only what a TFL session
  may use (log, tfl_output_dir, show_page, analyze_tfl); calls to the last
  two are recorded in hand_offs.
- INPUT_GUARD_SECONDS is set to 0 for the run so scripted answers are not
  swallowed; the guard has its own check with the real delay.
- Output goes to a temporary folder; APPDATA is set by the caller.
- Prints "GUI adapter double check passed", then the Results and
  scrolling confirmations; test_tfl.py looks for the first.

Edge cases
----------
- Exits non-zero on any failed assertion.
- Opening files goes through a recorded stand-in, so no application is
  launched.

Known limitations
-----------------
- Proves wiring and state flow only; it does not render pixels or test
  native focus, key bindings, selection by mouse, or window management.

Examples
--------
- python tests/gui_doubles_check.py
"""
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class Widget:
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        if name == "winfo_toplevel":
            return lambda: self
        if name == "winfo_exists":
            return lambda *a, **k: True
        if name == "winfo_children":
            return lambda *a, **k: []
        return lambda *a, **k: None


class Root(Widget):
    def winfo_width(self):
        return 800

    def winfo_height(self):
        return 600


class Var:
    def __init__(self, master=None, value=None):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


tk, ttk, messagebox, filedialog = MagicMock(), MagicMock(), MagicMock(), MagicMock()
tk.TclError = RuntimeError
tk.Toplevel = tk.Text = tk.Listbox = tk.Canvas = tk.Frame = tk.Label = Widget
tk.Tk = Root
tk.BooleanVar = tk.StringVar = tk.IntVar = Var
for name in ("Frame", "Label", "Button", "Checkbutton", "Spinbox", "Entry", "Style", "Scrollbar", "Progressbar"):
    setattr(ttk, name, Widget)
messagebox.askyesno.return_value = True
tk.ttk, tk.messagebox, tk.filedialog = ttk, messagebox, filedialog
sys.modules.update({"tkinter": tk, "tkinter.ttk": ttk, "tkinter.messagebox": messagebox,
                    "tkinter.filedialog": filedialog})

from types import SimpleNamespace  # noqa: E402

from gui.main_window import BrisartSuiteApp  # noqa: E402
from gui.pages.results_page import chronological_selection  # noqa: E402
from frameworks.TFL import gui_options, gui_session, settings  # noqa: E402
from frameworks.TFL.gui_session import TFLGuiSession  # noqa: E402

gui_session.INPUT_GUARD_SECONDS = 0

OUTPUT = Path(tempfile.mkdtemp())
KEY_ANSWERS = {"cue": "Return", "prediction": "a", "affect": "3", "perturbation": "Return",
               "post_perturbation_probe": "u", "behavioral_choice": "B", "content_probe": "U"}


def key(session, keysym):
    """Press and release one key, as the window would deliver it."""
    event = SimpleNamespace(keysym=keysym, widget=session.win)
    result = session.handle_key(event)
    session.release_key(event)
    return result


hand_offs = []
APP = SimpleNamespace(
    log=lambda text: None, tfl_output_dir=lambda: OUTPUT,
    show_page=lambda name: hand_offs.append(("page", name)),
    analyze_tfl=lambda path: hand_offs.append(("analyze", path)),
)


def new_session():
    session = TFLGuiSession(APP)
    session.win = Widget()
    gui_options.render_options(session)
    return session


# Options screen: defaults, invalid input blocks Start, valid options apply.
session = new_session()
assert session.summary_var.get().splitlines()[1] == "Run Configuration: Default TFL"
session.option_vars["trials_per_block"].set("0")
gui_options._start(session)
assert session.engine is None and "Trials Per Block" in session.error_var.get()
session.option_vars["trials_per_block"].set("10")
session.option_vars["enable_perturbations"].set(True)
session.option_vars["enable_response_timer"].set(True)
session.option_vars["trial_duration_sec"].set("15")
session.option_vars["blocks"]["affect"].set(False)
session.option_vars["session_label"].set("gui check")
key(session, "Return")  # Enter on the options screen starts the run
engine = session.engine
assert engine is not None and engine.config["run_mode"] == "modified_tfl" and engine.timer_seconds == 15
assert len(engine.trials) == 20 and {t["block"] for t in engine.trials} == {"belief", "contradiction"}
assert session.writer.path.name.startswith("tfl_output_gui_check_")

# Every screen publishes exactly the keys that answer it; the whole run is answered from the keyboard.
expected_keys = {"cue": {"return"}, "prediction": {"a", "b"}, "affect": {"1", "2", "3", "4", "5"},
                 "perturbation": {"return"},
                 "post_perturbation_probe": {"a", "b", "u"}, "behavioral_choice": {"a", "b"},
                 "content_probe": {"a", "b", "u"}}
seen = set()
while not engine.completed:
    stage = engine.active_stage()
    seen.add(stage)
    assert set(session.key_actions) == expected_keys[stage], (stage, session.key_actions)
    if stage == "affect":
        for useless in ("x", "0", "6", "Return", "a"):   # only 1 to 5 answer affect; Enter and letters do nothing
            assert key(session, useless) is None and engine.active_stage() == "affect", useless
    before = (len(engine.rows), stage)
    assert key(session, KEY_ANSWERS[stage]) == "break"
    assert (len(engine.rows), engine.active_stage()) != before, stage
assert seen == set(expected_keys), seen
assert session.finished and session.writer.closed and session.writer.rows_saved == 20
assert hand_offs == [("page", "Results"), ("analyze", session.writer.path)], hand_offs  # finished run -> Results
assert set(session.key_actions) == {"return"}  # completion screen: Enter closes
import csv  # noqa: E402
saved = list(csv.DictReader(session.writer.path.open(encoding="utf-8")))
assert {row["prediction"] for row in saved} <= {"A", ""} and {row["behavioral_choice"] for row in saved} <= {"B", ""}
assert {row["affect"] for row in saved} == {"50"}   # the key 3 is the third value, 50

# Held-key guard: a held key acts once until released; focus loss forgets held keys.
presses = []
session.key_actions = {"a": lambda: presses.append("a")}
held = SimpleNamespace(keysym="a", widget=session.win)
assert session.handle_key(held) == "break" and session.handle_key(held) is None
session.release_key(held)
assert session.handle_key(held) == "break" and presses == ["a", "a"]
assert session.handle_key(held) is None  # still held
session.forget_held_keys(SimpleNamespace(widget=session.win))
assert session.handle_key(held) == "break" and len(presses) == 3
assert "Saved 20 trials" in session.completion_message

# Restore defaults, answer partway, cancel: answers stay on disk.
session = new_session()
session.option_vars["trials_per_block"].set("3")
gui_options._restore(session)
gui_options._start(session)
assert session.engine.config["run_mode"] == "default_tfl" and len(session.engine.trials) == 120
key(session, "Return")
key(session, "b")
assert key(session, "Escape") == "break"  # Esc stops the run after confirmation
assert session.engine.cancelled and session.writer.closed
lines = session.writer.path.read_text(encoding="utf-8").splitlines()
assert len(lines) == 2 and lines[1].endswith(",in_progress")
# Archive window: every page renders, TFL launches once, closing mid-run keeps answers.
app = BrisartSuiteApp()
logs = []
app.log = logs.append
for page in ("Dashboard", "TFL", "Results", "Archive", "Settings", "Frameworks"):
    app.show_page(page)
assert not [line for line in logs if "could not be displayed" in line], logs
app.tfl_output_dir = lambda: OUTPUT
app.start_tfl()
first = app.tfl_session
app.start_tfl()
assert app.tfl_session is first
gui_options._start(first)
first.engine.continue_cue()
first.engine.submit_prediction("A")
first.after_input()
app.on_close()
assert first.writer.closed and first.engine.cancelled
assert len(first.writer.path.read_text(encoding="utf-8").splitlines()) == 2
print("GUI adapter double check passed")

# Affect: every key 1 to 5 (and the keypad digits) records its own value and moves straight on.
values = {}
for keysym, expected in (("1", 0), ("2", 25), ("3", 50), ("4", 75), ("5", 100),
                         ("KP_1", 0), ("KP_2", 25), ("KP_3", 50), ("KP_4", 75), ("KP_5", 100)):
    probe = new_session()
    probe.option_vars["trials_per_block"].set("1")
    probe.option_vars["blocks"]["affect"].set(True)
    key(probe, "Return")
    key(probe, "Return")
    key(probe, "a")
    assert probe.engine.active_stage() == "affect"
    assert key(probe, keysym) == "break"
    assert probe.engine.response["affect"] == expected, (keysym, probe.engine.response["affect"])
    assert probe.engine.active_stage() == "behavioral_choice"     # no Continue step
    assert set(probe.key_actions) == {"a", "b"}                    # the screen has already changed
    probe.end_run("check")
    values[keysym] = expected
assert sorted(set(values.values())) == list(settings.AFFECT_CHOICES)

# Input guard: an answer right after a screen is drawn is ignored (a double-click cannot answer the next
# question); once the guard has passed, the same answer is accepted. Esc and F11 are never guarded.
gui_session.INPUT_GUARD_SECONDS = 60
guarded = new_session()
guarded.option_vars["trials_per_block"].set("1")
key(guarded, "Return")                       # options screen is not guarded; the run starts
assert guarded.engine.active_stage() == "cue"
assert not guarded.accepting_input()
assert key(guarded, "Return") == "break" and guarded.engine.active_stage() == "cue"   # swallowed
guarded._ready_at = 0
assert guarded.accepting_input()
assert key(guarded, "Return") == "break" and guarded.engine.active_stage() == "prediction"
assert not guarded.accepting_input()                                                   # the new screen guards again
assert key(guarded, "a") == "break" and guarded.engine.active_stage() == "prediction"
assert guarded.engine.response["prediction"] == ""
assert key(guarded, "F11") == "break"        # not guarded
guarded.end_run("check")
gui_session.INPUT_GUARD_SECONDS = 0
print("Affect buttons and input guard checks passed")

# Results page: one session, several sessions (pooled), nothing selected, newest by default.
from frameworks.TFL.headless import build_engine  # noqa: E402
from frameworks.TFL.output import SessionWriter, list_session_files  # noqa: E402
second = SessionWriter(OUTPUT, label="second")
engine2, _ = build_engine({"trials_per_block": 2, "blocks": "belief"}, on_progress=second.save)
while not engine2.completed:
    stage = engine2.active_stage()
    if stage == "cue":
        engine2.continue_cue()
    else:
        method, value = {"prediction": ("submit_prediction", "B"), "affect": ("submit_affect", "25"),
                         "behavioral_choice": ("submit_behavioral_choice", "A"),
                         "content_probe": ("submit_content_probe", "U")}[stage]
        getattr(engine2, method)(value)
second.close()
reports = []
app.set_analysis_text = reports.append
from frameworks.TFL import analysis  # noqa: E402
complete = [p for p in list_session_files(OUTPUT) if analysis.split_by_status(analysis.load_output(p))[0]]
assert len(complete) >= 2, complete
app.analyze_tfl()
assert reports[-1].startswith("TFL Analysis"), reports[-1][:80]            # newest session, reference report
app.analyze_tfl([complete[0]])
assert reports[-1].startswith("TFL Analysis")                              # one chosen file = reference report
app.analyze_tfl(complete[:2])
assert reports[-1].startswith("TFL Combined Analysis") and "Files analyzed: 2" in reports[-1]
app.analyze_tfl([])
assert "Select one or more sessions" in reports[-1]                         # nothing selected: guidance, no crash
assert chronological_selection(["c", "b", "a"], (0, 2)) == ["a", "c"]       # newest-first list -> oldest first
assert chronological_selection(["c", "b", "a"], (2, 0, 1)) == ["a", "b", "c"]
shown = []
import controllers.system_controller as sc  # noqa: E402
sc.open_with_system = shown.append
app.open_tfl_csvs(complete[:2])
assert shown == complete[:2]
app._fail = lambda title, message: shown.append(title)
app.open_tfl_csvs([])
app.open_tfl_csvs(complete * sc.MAX_CSVS_AT_ONCE)
assert shown[-2:] == ["Nothing Selected", "Too Many Files"], shown
print("Results page selection checks passed")

from unittest.mock import Mock  # noqa: E402
view = session.options_viewport
view.canvas = Mock()
view.canvas.yview.return_value = (0.0, 0.25)
child = SimpleNamespace(master=view)
assert view._wheel(SimpleNamespace(widget=child, delta=-120)) == "break"
view.canvas.yview_scroll.assert_called_once_with(1, "units")
view.canvas.reset_mock()
assert view._wheel(SimpleNamespace(widget=SimpleNamespace(master=None), delta=-120)) is None
view.canvas.yview_scroll.assert_not_called()
view.canvas.yview.return_value = (0.0, 1.0)
assert view._wheel(SimpleNamespace(widget=child, delta=-1)) == "break"
view.canvas.yview_scroll.assert_not_called()
view._top = Mock()
view._bindings = [("<MouseWheel>", "binding-id")]
view._cleanup(SimpleNamespace(widget=view))
view._top.unbind.assert_called_once_with("<MouseWheel>", "binding-id")
assert view._bindings == []
app._page_canvas = Mock()
app.winfo_containing = lambda *args: SimpleNamespace(master=None)
app._on_global_mousewheel(SimpleNamespace(x_root=0, y_root=0, delta=-120))
app._page_canvas.yview_scroll.assert_not_called()
print("Scrollbar routing and binding cleanup checks passed")

