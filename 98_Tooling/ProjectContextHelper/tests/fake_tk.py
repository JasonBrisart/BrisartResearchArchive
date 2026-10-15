"""
File: tests/fake_tk.py

Purpose
-------
Provide a minimal recording stand-in for tkinter so GUI wiring can be exercised headlessly.

Communication / relationships
-----------------------------
Installed into sys.modules as tkinter/tkinter.ttk/filedialog/messagebox by tests/test_gui_wiring.py
subprocesses only. No application module imports this file.

Settings / parameters
---------------------
REGISTRY records widgets; MESSAGES records dialogs; ASK_ANSWER controls askyesno; FOLDER controls
askdirectory. Tk.after queues callbacks for run_pending().

Edge cases
----------
Unknown widget methods are accepted as no-ops so layout calls do not fail.

Known limitations
-----------------
Does not render, measure, or emulate real Tk event semantics, threading rules, fonts, or
platform behavior. Passing wiring tests is not physical GUI validation.

Examples
--------
Usage from the directory containing run.py:

    python -m unittest discover -s tests -p test_gui_wiring.py -v
"""
import time
import types

REGISTRY = []
MESSAGES = []
ASK_ANSWER = [True]
FOLDER = ['']
ROOT = []


class _Var:
    def __init__(self, master=None, value=None):
        self._value = value
        self._traces = []

    def get(self):
        return self._value

    def set(self, value):
        self._value = value
        for callback in list(self._traces):
            callback('', '', 'write')

    def trace_add(self, _mode, callback):
        self._traces.append(callback)


class StringVar(_Var):
    def __init__(self, master=None, value=''):
        super().__init__(master, value)


class BooleanVar(_Var):
    def __init__(self, master=None, value=False):
        super().__init__(master, bool(value))

    def set(self, value):
        super().set(bool(value))


class IntVar(_Var):
    pass


class Widget:
    def __init__(self, master=None, **options):
        self.master = master
        self.options = dict(options)
        self.kind = type(self).__name__
        self.items = {}
        self.order = []
        self.selected = ()
        REGISTRY.append(self)

    def config(self, **options):
        self.options.update(options)

    configure = config

    def cget(self, key):
        return self.options.get(key)

    def __setitem__(self, key, value):
        self.options[key] = value

    def __getitem__(self, key):
        return self.options.get(key)

    def __getattr__(self, name):
        return lambda *args, **kwargs: None

    def invoke(self):
        if self.options.get('state') == 'disabled':
            return None
        return self.options['command']()

    # Treeview subset
    def insert(self, parent, index, values=()):
        item = f'I{len(self.order) + 1}'
        self.items[item] = values
        self.order.append(item)
        return item

    def delete(self, *items):
        for item in items:
            self.items.pop(item, None)
            if item in self.order:
                self.order.remove(item)

    def get_children(self, *_args):
        return tuple(self.order)

    def selection(self):
        return self.selected

    def bbox(self, *_args):
        return (0, 0, 1, 1)

    def create_window(self, *_args, **_kwargs):
        return 1


class Tk(Widget):
    def __init__(self, *args, **kwargs):
        super().__init__(None)
        self.pending = []
        self.destroyed = False
        self.protocols = {}
        ROOT.append(self)

    def after(self, _ms, callback=None):
        self.pending.append(callback)
        return f'after{len(self.pending)}'

    def protocol(self, name, callback):
        self.protocols[name] = callback

    def destroy(self):
        self.destroyed = True
        self.pending.clear()

    def mainloop(self):
        return None

    def run_pending(self, timeout=20.0):
        deadline = time.monotonic() + timeout
        while self.pending and not self.destroyed:
            if time.monotonic() > deadline:
                raise TimeoutError('after() queue did not settle')
            callback = self.pending.pop(0)
            callback()
            time.sleep(0.01)


for _name in ('Frame', 'Label', 'Button', 'Entry', 'LabelFrame', 'Scrollbar', 'Canvas', 'Checkbutton', 'Text', 'Spinbox'):
    globals()[_name] = type(_name, (Widget,), {})

ttk = types.ModuleType('tkinter.ttk')
for _name in ('Notebook', 'Combobox', 'Treeview', 'Frame', 'Label', 'Button', 'Scrollbar', 'Progressbar'):
    setattr(ttk, _name, type(_name, (Widget,), {}))

filedialog = types.ModuleType('tkinter.filedialog')
filedialog.askdirectory = lambda **_kwargs: FOLDER[0]

messagebox = types.ModuleType('tkinter.messagebox')


def _record(kind):
    def show(title, message=''):
        MESSAGES.append((kind, title, message))
        return ASK_ANSWER[0] if kind == 'askyesno' else None
    return show


for _kind in ('showinfo', 'showwarning', 'showerror', 'askyesno'):
    setattr(messagebox, _kind, _record(_kind))


def install():
    import sys
    module = sys.modules[__name__]
    sys.modules['tkinter'] = module
    sys.modules['tkinter.ttk'] = ttk
    sys.modules['tkinter.filedialog'] = filedialog
    sys.modules['tkinter.messagebox'] = messagebox
    module.ttk = ttk
    module.filedialog = filedialog
    module.messagebox = messagebox


def buttons(text):
    return [w for w in REGISTRY if w.kind == 'Button' and w.options.get('text') == text]
