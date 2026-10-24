"""
File: tests/tfl_gui_doubles_check.py

Purpose
-------
Drive the TFL GUI adapter (options screen, trial screens, completion,
cancel) end to end with stand-in widget classes, so GUI wiring is
exercised on machines without Tk.

Communication / relationships
-----------------------------
- Run in its own interpreter by tests/test_tfl_protocol.py, because it
  replaces tkinter in sys.modules.
- Imports frameworks/TFL/session_gui.py and options_screen.py.

Settings / parameters
---------------------
- Widget doubles: every ttk widget is a no-op object; variables store
  values. The writer uses a temporary output folder.

Edge cases
----------
- Exits non-zero on any assertion failure.

Known limitations
-----------------
- Proves wiring and state flow only; it does not render pixels or test
  native focus, key bindings, or window management.

Examples
--------
- python tests/tfl_gui_doubles_check.py
"""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unittest.mock import MagicMock
class W:
    def __init__(self, *a, **k): self.k = k
    def __getattr__(self, name): return lambda *a, **k: True if name == "winfo_exists" else ([] if name == "winfo_children" else None)
class Var:
    def __init__(self, master=None, value=None): self.v = value
    def get(self): return self.v
    def set(self, v): self.v = v
tk = MagicMock(); ttk = MagicMock(); mb = MagicMock()
tk.TclError = RuntimeError; tk.Toplevel = W; tk.Tk = W
tk.BooleanVar = tk.StringVar = tk.IntVar = Var
for n in ("Frame","Label","Button","Checkbutton","Spinbox","Entry"): setattr(ttk, n, W)
tk.ttk = ttk; tk.messagebox = mb
sys.modules.update({"tkinter": tk, "tkinter.ttk": ttk, "tkinter.messagebox": mb})
from frameworks.TFL.session_gui import TFLGuiSession
from frameworks.TFL import options_screen
s = TFLGuiSession(); s.log = lambda text: None; s.win = W()
s._output_dir = lambda: tempfile.mkdtemp()
options_screen.render_options(s)
assert s.summary_var.get().splitlines()[1] == "Run Configuration: Default TFL"
s.option_vars["enable_perturbations"].set(True); s.option_vars["enable_response_timer"].set(True)
s.timer_seconds_var.set("15")
options_screen._start(s)
e = s.engine
assert (e.config["run_mode"], e.timer_seconds) == ("modified_tfl", 15)
ans = {"prediction":"A","post_perturbation_probe":"U","behavioral_choice":"B","content_probe":"U"}
m = {"prediction":"submit_prediction","post_perturbation_probe":"submit_post_perturbation_probe","behavioral_choice":"submit_behavioral_choice","content_probe":"submit_content_probe"}
n = 0
while not e.completed:
    st = e.active_stage()
    if st == "cue": e.continue_cue()
    elif st == "affect": e.submit_affect("55")
    elif st == "perturbation": e.continue_perturbation()
    else: getattr(e, m[st])(ans[st])
    s.after_input(); n += 1
assert s.finished and s.writer.rows_written == 120 and s.writer.finalized
s2 = TFLGuiSession(); s2.log = lambda text: None; s2.win = W(); s2._output_dir = lambda: tempfile.mkdtemp()
options_screen.render_options(s2); options_screen._restore_defaults(s2); options_screen._start(s2)
for _ in range(3): s2.engine.continue_cue(); s2.after_input(); s2.engine.submit_prediction("A"); s2.engine.submit_affect("5"); s2.engine.submit_behavioral_choice("B"); s2.after_input()
s2.cancel()
assert s2.writer.rows_written == 3 and s2.writer.closed and not s2.writer.finalized
assert s2.engine.config["run_mode"] == "default_tfl"
print("GUI adapter double check passed")
