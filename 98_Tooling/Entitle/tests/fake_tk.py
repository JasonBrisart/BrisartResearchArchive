"""
File: tests/fake_tk.py

Purpose
-------
Stand in for tkinter so tests/test_gui.py can run the real gui/ modules without a display. It
  records every widget, runs button commands on request, remembers what the output pane and the
  error dialogs show, and raises on any widget method it does not implement, so a wiring
  mistake in gui/ fails a test instead of being ignored.

Communication / relationships
-----------------------------
Imported only by tests/test_gui.py, which installs modules() into sys.modules as tkinter,
  tkinter.ttk, tkinter.filedialog, tkinter.messagebox and tkinter.scrolledtext for the length
  of one test. No application module imports it.

Settings / parameters
---------------------
REGISTRY holds every widget created, NOTEBOOKS every notebook (its tabs are (frame, text)
  pairs), MESSAGES every (kind, title, text) dialog, and DIALOG_FILE[0] what the file dialogs
  return. buttons(text) finds buttons by label; Widget.invoke() runs a button's command.
  ScrolledText keeps what was inserted in .text. reset() clears all of it.

Edge cases
----------
Layout methods (pack, grid, grid_columnconfigure, configure) are accepted and ignored;
  anything else a widget is asked to do that is not implemented raises AttributeError.
  TclError is provided so tests can simulate "no display".

Known limitations
-----------------
It does not draw, measure or follow real Tk event rules. Passing tests prove wiring and
  behavior, not appearance.

Examples
--------
From the directory containing main.py:

    python -m pytest tests/test_gui.py
"""

import types

REGISTRY = []
NOTEBOOKS = []
MESSAGES = []
DIALOG_FILE = [""]


def reset():
    REGISTRY.clear()
    NOTEBOOKS.clear()
    MESSAGES.clear()
    DIALOG_FILE[0] = ""


class TclError(Exception):
    pass


class _Var:
    def __init__(self, master=None, value=None):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


class StringVar(_Var):
    def __init__(self, master=None, value=""):
        super().__init__(master, value)


class BooleanVar(_Var):
    def __init__(self, master=None, value=False):
        super().__init__(master, bool(value))


class Widget:
    def __init__(self, master=None, **options):
        self.master = master
        self.options = dict(options)
        self.kind = type(self).__name__
        REGISTRY.append(self)

    def pack(self, *args, **kwargs):
        return None

    def grid(self, *args, **kwargs):
        return None

    def grid_columnconfigure(self, *args, **kwargs):
        return None

    def configure(self, **options):
        self.options.update(options)

    config = configure

    def invoke(self):
        return self.options["command"]()


class Tk(Widget):
    def __init__(self, *args, **kwargs):
        super().__init__(None)
        self.window_title = ""

    def title(self, text):
        self.window_title = text

    def geometry(self, spec):
        return None

    def minsize(self, width, height):
        return None

    def mainloop(self):
        return None


class Notebook(Widget):
    def __init__(self, master=None, **options):
        super().__init__(master, **options)
        self.tabs = []
        NOTEBOOKS.append(self)

    def add(self, frame, text=""):
        self.tabs.append((frame, text))


class ScrolledText(Widget):
    def __init__(self, master=None, **options):
        super().__init__(master, **options)
        self.text = ""

    def delete(self, start, end):
        self.text = ""

    def insert(self, index, text):
        self.text += text


def _simple(name):
    return type(name, (Widget,), {})


tk = types.ModuleType("tkinter")
tk.Tk = Tk
tk.StringVar = StringVar
tk.BooleanVar = BooleanVar
tk.TclError = TclError

ttk = types.ModuleType("tkinter.ttk")
ttk.Notebook = Notebook
for _name in ("Frame", "Label", "Entry", "Checkbutton", "Button"):
    setattr(ttk, _name, _simple(_name))

filedialog = types.ModuleType("tkinter.filedialog")
filedialog.askopenfilename = lambda **kwargs: DIALOG_FILE[0]
filedialog.asksaveasfilename = lambda **kwargs: DIALOG_FILE[0]

messagebox = types.ModuleType("tkinter.messagebox")
messagebox.showerror = lambda title, message="": MESSAGES.append(("showerror", title, message))

scrolledtext = types.ModuleType("tkinter.scrolledtext")
scrolledtext.ScrolledText = ScrolledText

tk.ttk = ttk
tk.filedialog = filedialog
tk.messagebox = messagebox
tk.scrolledtext = scrolledtext


def modules():
    return {
        "tkinter": tk,
        "tkinter.ttk": ttk,
        "tkinter.filedialog": filedialog,
        "tkinter.messagebox": messagebox,
        "tkinter.scrolledtext": scrolledtext,
    }


def buttons(text):
    return [w for w in REGISTRY if w.kind == "Button" and w.options.get("text") == text]
