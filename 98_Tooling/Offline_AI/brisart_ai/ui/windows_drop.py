r"""
File: brisart_ai/ui/windows_drop.py

Purpose
-------
Receive Explorer file and folder drops for the Add Sources queue.

The Windows drop bridge exists because standard Tk does not provide the Explorer
filesystem drop behavior required by Add Sources. It is platform-specific and does not
belong in the cross-platform reader.

Internal helpers include ExplorerDrop.__init__.

Communication / relationships
-----------------------------
The Windows callback queues paths while the Tk dialog polls on the UI thread.

A Windows subclass callback receives paths and queues them; the Tk dialog polls the
queue on its own thread. The callback must not call Tk.

No direct project import appears in this module’s top-level imports. The file is reached
as a launcher, test, or helper, or through a runtime import rather than through an
ordinary domain import.

Concrete calls within this file include self.paths.append.

Settings / parameters
---------------------
ExplorerDrop accepts an HWND on the owning UI thread.

This file has no independently configurable runtime parameters. The values it exports
are consumed by its owner rather than loaded from another settings file.

Edge cases
----------
Drop handles are released and the subclass is removed when the widget is destroyed.

Shell handles must always be released and the subclass removed when the window is
destroyed. Windows privilege boundaries can prevent Explorer drops.

Explicit exception branches or raised errors in this file include OSError.

Known limitations
-----------------
Windows Explorer-style filesystem drops only; Browse is the fallback.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Any broader behavior
depends on the documented upstream inputs and downstream consumers. No compatibility adapter
or speculative extension point has been added as part of this pass.

Examples
--------
ExplorerDrop(widget.winfo_id())

For a concrete entry point, inspect `ExplorerDrop`; invoke it through the existing application
entry point or its documented caller. The example above is illustrative of this file's present
interface; do not treat it as an instruction to create additional state or call private
functions directly.
"""
from collections import deque
import ctypes as c
from ctypes import wintypes as w


class ExplorerDrop:
    def __init__(self, hwnd):
        self.paths = deque()
        shell = c.WinDLL("shell32", use_last_error=True)
        controls = c.WinDLL("comctl32", use_last_error=True)
        callback = c.WINFUNCTYPE(c.c_ssize_t, w.HWND, w.UINT, w.WPARAM,
                                 w.LPARAM, c.c_size_t, c.c_size_t)
        shell.DragAcceptFiles.argtypes = (w.HWND, w.BOOL)
        shell.DragAcceptFiles.restype = None
        shell.DragQueryFileW.argtypes = (w.HANDLE, w.UINT, w.LPWSTR, w.UINT)
        shell.DragQueryFileW.restype = w.UINT
        shell.DragFinish.argtypes = (w.HANDLE,)
        shell.DragFinish.restype = None
        controls.SetWindowSubclass.argtypes = (w.HWND, callback, c.c_size_t, c.c_size_t)
        controls.SetWindowSubclass.restype = w.BOOL
        controls.RemoveWindowSubclass.argtypes = (w.HWND, callback, c.c_size_t)
        controls.RemoveWindowSubclass.restype = w.BOOL
        controls.DefSubclassProc.argtypes = (w.HWND, w.UINT, w.WPARAM, w.LPARAM)
        controls.DefSubclassProc.restype = c.c_ssize_t
        tag = id(self)

        @callback
        def on_message(window, message, wp, lp, _tag, _data):
            if message == 0x0233:  # WM_DROPFILES
                try:
                    for i in range(shell.DragQueryFileW(wp, 0xFFFFFFFF, None, 0)):
                        length = shell.DragQueryFileW(wp, i, None, 0)
                        if length:
                            path = c.create_unicode_buffer(length + 1)
                            if shell.DragQueryFileW(wp, i, path, len(path)):
                                self.paths.append(path.value)
                finally:
                    shell.DragFinish(wp)
                return 0
            if message == 0x0082:  # WM_NCDESTROY
                shell.DragAcceptFiles(window, False)
                controls.RemoveWindowSubclass(window, on_message, tag)
            return controls.DefSubclassProc(window, message, wp, lp)

        self._callback = on_message
        if not controls.SetWindowSubclass(hwnd, on_message, tag, 0):
            raise OSError("Could not register the Explorer drop target")
        shell.DragAcceptFiles(hwnd, True)
