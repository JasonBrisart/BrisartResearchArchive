"""
File: tests/gui_doubles_check.py

Purpose
-------
Drive the GUI end to end with stand-in widget classes: the Archive
window and every page, then the TFL options screen, every trial screen,
completion, cancel, and closing the Archive during a run. This exercises
the GUI wiring on machines without Tk.

Communication / relationships
-----------------------------
- Run in its own interpreter by tests/test_tfl.py, because it replaces
  tkinter in sys.modules.
- Imports gui/main_window.py (and through it every page and controller)
  and frameworks/TFL/gui_session.py, frameworks/TFL/gui_options.py, and frameworks/TFL/gui_screens.py.

Settings / parameters
---------------------
- Widget: accepts any call and returns None (winfo_exists returns True,
  winfo_children returns []).
- Var: stores a value like a Tk variable.
- Output goes to a temporary folder.

Edge cases
----------
- Exits non-zero on any failed assertion.

Known limitations
-----------------
- Proves wiring and state flow only; it does not render pixels or test
  native focus, key bindings, or window management.

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
tk.Toplevel = tk.Text = tk.Canvas = tk.Frame = tk.Label = Widget
tk.Tk = Root
tk.BooleanVar = tk.StringVar = tk.IntVar = Var
for name in ("Frame", "Label", "Button", "Checkbutton", "Spinbox", "Entry", "Style", "Scrollbar"):
    setattr(ttk, name, Widget)
messagebox.askyesno.return_value = True
tk.ttk, tk.messagebox, tk.filedialog = ttk, messagebox, filedialog
sys.modules.update({"tkinter": tk, "tkinter.ttk": ttk, "tkinter.messagebox": messagebox,
                    "tkinter.filedialog": filedialog})

from gui.main_window import BrisartSuiteApp  # noqa: E402
from frameworks.TFL import gui_options  # noqa: E402
from frameworks.TFL.gui_session import TFLGuiSession  # noqa: E402

OUTPUT = Path(tempfile.mkdtemp())


def new_session():
    session = TFLGuiSession()
    session.log = lambda text: None
    session.win = Widget()
    session._output_dir = lambda: OUTPUT
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
gui_options._start(session)
engine = session.engine
assert engine is not None and engine.config["run_mode"] == "modified_tfl" and engine.timer_seconds == 15
assert len(engine.trials) == 20 and {t["block"] for t in engine.trials} == {"belief", "contradiction"}
assert session.writer.path.name.startswith("tfl_output_gui_check_")

answers = {"prediction": ("submit_prediction", "A"), "affect": ("submit_affect", "55"),
           "post_perturbation_probe": ("submit_post_perturbation_probe", "U"),
           "behavioral_choice": ("submit_behavioral_choice", "B"), "content_probe": ("submit_content_probe", "U")}
while not engine.completed:
    stage = engine.active_stage()
    if stage == "cue":
        engine.continue_cue()
    elif stage == "perturbation":
        engine.continue_perturbation()
    else:
        method, value = answers[stage]
        getattr(engine, method)(value)
    session.after_input()
assert session.finished and session.writer.closed and session.writer.rows_saved == 20
assert "Saved 20 trials" in session.completion_message

# Restore defaults, answer partway, cancel: answers stay on disk.
session = new_session()
session.option_vars["trials_per_block"].set("3")
gui_options._restore(session)
gui_options._start(session)
assert session.engine.config["run_mode"] == "default_tfl" and len(session.engine.trials) == 120
session.engine.continue_cue()
session.engine.submit_prediction("B")
session.after_input()
session.cancel()
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
first._output_dir = lambda: OUTPUT
gui_options._start(first)
first.engine.continue_cue()
first.engine.submit_prediction("A")
first.after_input()
app.on_close()
assert first.writer.closed and first.engine.cancelled
assert len(first.writer.path.read_text(encoding="utf-8").splitlines()) == 2
print("GUI adapter double check passed")
