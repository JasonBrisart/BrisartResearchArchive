"""Receive Explorer file and folder drops on a Tk widget.

Purpose
-------
Bridge the Windows shell's WM_DROPFILES message to the Add Sources queue.

Communication / relationships
-----------------------------
The dialog polls the queue on the Tk thread; the native callback does not
call Tk. Windows unregisters the subclass when the drop widget is destroyed.

Settings / parameters
---------------------
ExplorerDrop accepts an HWND owned by the current UI thread.

Edge cases
----------
A drop always releases its shell handle, even if path decoding fails.

Known limitations
-----------------
Only Windows Explorer-style filesystem drops are supported. Use Browse on
other platforms or when Windows blocks drops between privilege levels.

Examples
--------
Keep ExplorerDrop(widget.winfo_id()) alive until the widget is destroyed.
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
