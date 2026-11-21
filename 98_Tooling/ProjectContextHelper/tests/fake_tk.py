"""
File: tests/fake_tk.py

Purpose
-------
Stand in for tkinter so tests/test_gui.py can run the real gui/ modules without a display. It
  records every widget created and every message shown, runs after() callbacks on demand, and
  lets a test click buttons and answer yes/no prompts.

Communication / relationships
-----------------------------
Installed into sys.modules as tkinter, tkinter.ttk, tkinter.filedialog, and
  tkinter.messagebox by install(), only inside tests/test_gui.py scenario processes. No
  application module imports it. tests/support.py holds the setup shared by real test files.

Settings / parameters
---------------------
REGISTRY holds every widget, MESSAGES every (kind, title, text) dialog, ASK_ANSWER[0] the
  answer to askyesno, and FOLDER[0] what askdirectory returns. Tk.run_pending() runs queued
  after() callbacks until none remain or the timeout passes. buttons(text) finds buttons by
  label; Widget.invoke() honors state="disabled". Widget.visible is True after pack() or
  grid(), False after pack_forget() or grid_remove(), and None if never placed.
  Widget.calls records every other method call as (name, args, kwargs), for example the
  Notebook's tab(frame, state="hidden") or a Canvas's yview_moveto(0). Widget.dimensions
  holds the width, height, and requested height that winfo_width(), winfo_height(), and
  winfo_reqheight() report (1 until a test sets them, like an unplaced Tk window).
  Widget.bind() stores callbacks and Widget.fire(sequence, **event) runs one. Text keeps its
  content, tracks the modified flag, and Text.user_edit(text) plays a person typing.
  Layout model: Widget.requested_height() stacks the heights and pady of a frame's placed
  children (Widget.children, Widget.visible) and is what winfo_reqheight() reports unless a test
  sets dimensions['reqheight']. It copies one real Tk rule: a frame whose last placed child is
  removed keeps its previous height. A test that hides a section must therefore measure the
  frame that holds it, not recompute the expected height itself.

Edge cases
----------
Any widget method it does not implement is accepted and recorded in Widget.calls, so other
  layout and binding calls never fail.

Known limitations
-----------------
Does not draw, measure, or follow real Tk event or threading rules. Passing GUI tests proves
  wiring and behavior, not appearance.

Examples
--------
From the directory containing run.py:

    python -m unittest discover -s tests -p test_gui.py -v
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


CONTAINERS = ('Frame', 'LabelFrame')
LEAF_HEIGHT = 20


def _pad(options, key='pady'):
    value = options.get(key) or 0
    return sum(value) if isinstance(value, (tuple, list)) else value


class Widget:
    def __init__(self, master=None, **options):
        self.calls = []
        self.bindings = {}
        self.dimensions = {'width': 1, 'height': 1, 'reqheight': None}
        self.master = master
        self.options = dict(options)
        self.kind = type(self).__name__
        self.items = {}
        self.order = []
        self.selected = ()
        self.visible = None
        self.children = []
        self.pack_options = {}
        self.last_request = 1
        if master is not None:
            master.children.append(self)
        if self.kind in CONTAINERS and (options.get('height') or 0) > 0:
            self.last_request = options['height']
        REGISTRY.append(self)

    def config(self, **options):
        self.options.update(options)
        if self.kind in CONTAINERS and (options.get('height') or 0) > 0 and not self.placed_children():
            self.last_request = options['height']
            self.arrange_master()

    # Layout model. Every placed child of a frame adds its own height and pady (a stack: enough
    # to tell whether space is released, not pixel-accurate). The one rule copied from Tk
    # itself: a frame whose LAST placed child is removed stops managing its size and keeps its
    # previous requested height, so a frame that is not given another child never shrinks.
    def placed_children(self):
        return [child for child in self.children if child.visible]

    def requested_height(self):
        if self.kind in CONTAINERS:
            return self.last_request
        if self.kind == 'Text':
            return 16 * (self.options.get('height') or 1)
        if self.kind == 'Treeview':
            return 18 * (self.options.get('height') or 1)
        return self.options.get('height') or LEAF_HEIGHT

    def arrange(self):
        placed = self.placed_children()
        if not placed:
            return
        label = 18 if self.kind == 'LabelFrame' else 0
        self.last_request = label + 2 * _pad(self.options) + sum(child.requested_height() + _pad(child.pack_options) for child in placed)
        self.arrange_master()

    def arrange_master(self):
        if self.master is not None and self.visible:
            self.master.arrange()

    configure = config

    def cget(self, key):
        return self.options.get(key)

    def __setitem__(self, key, value):
        self.options[key] = value

    def __getitem__(self, key):
        return self.options.get(key)

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)

        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))
        return record

    # Sizes a test can set: Tk reports 1 until a window has been placed.
    def winfo_width(self):
        return self.dimensions['width']

    def winfo_height(self):
        return self.dimensions['height']

    def winfo_reqheight(self):
        override = self.dimensions['reqheight']
        return override if override is not None else self.requested_height()

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = callback

    def fire(self, sequence, **event):
        """Run the callback bound to sequence with a fake event carrying the given fields."""
        return self.bindings[sequence](types.SimpleNamespace(**event))

    # Geometry: record whether the widget is currently placed, for show/hide checks.
    def pack(self, *args, **kwargs):
        self.visible = True
        self.pack_options = kwargs
        if self.master is not None:
            self.master.arrange()

    grid = pack

    def pack_forget(self):
        self.visible = False
        if self.master is not None:
            self.master.arrange()

    grid_remove = pack_forget

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

    def create_window(self, *args, **kwargs):
        self.calls.append(('create_window', args, kwargs))
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


class Text(Widget):
    """Holds text like a Tk Text; user_edit() plays a person typing, which raises <<Modified>>."""

    def __init__(self, master=None, **options):
        super().__init__(master, **options)
        self.content = ''
        self.modified = False

    def get(self, *_args):
        return self.content

    def insert(self, _index, text):
        self.content = text + self.content if _index == '1.0' else self.content + text
        self.modified = True

    def delete(self, *_args):
        self.content = ''
        self.modified = True

    def edit_modified(self, flag=None):
        if flag is None:
            return self.modified
        self.modified = bool(flag)

    def user_edit(self, text):
        self.content = text
        self.modified = True
        self.fire('<<Modified>>')


for _name in ('Frame', 'Label', 'Button', 'Entry', 'LabelFrame', 'Scrollbar', 'Canvas', 'Checkbutton', 'Spinbox'):
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