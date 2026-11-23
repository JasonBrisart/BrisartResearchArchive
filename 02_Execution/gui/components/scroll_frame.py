"""
File: gui/components/scroll_frame.py

Purpose
-------
Provide ScrollFrame, a vertically scrollable content area with a
permanently visible scrollbar, for screens whose content can be taller
than a small window.

Communication / relationships
-----------------------------
- Used by the TFL options screen (frameworks/TFL/gui_options.py), which
  builds its option cards inside ScrollFrame.content.
- Uses COLORS from gui/theme.py and mousewheel_units() from
  gui/components/page_helpers.py.
- Its wheel bindings belong to the window that contains it, not to the
  application, so it never competes with the page-level scrolling in
  gui/main_window.py.

Settings / parameters
---------------------
- ScrollFrame(parent) exposes content (the frame to build into), canvas,
  and scrollbar.
- Handles <MouseWheel>, <Button-4>, and <Button-5> on its Toplevel.

Edge cases
----------
- A wheel event is used only when it comes from a widget inside this frame.
- A fully visible body does not move.
- The content width follows the viewport width, and the scroll region
  follows the content height.
- Destroying the frame removes only the bindings it added, leaving other
  window handlers in place.

Known limitations
-----------------
- Vertical scrolling only.
- Touchpad support depends on the wheel events the local Tk build delivers
  (see the limitation in gui/components/page_helpers.py).

Examples
--------
- view = ScrollFrame(parent); view.pack(fill="both", expand=True)
- ttk.Label(view.content, text="Row").pack()
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from gui.theme import COLORS
from gui.components.page_helpers import mousewheel_units

class ScrollFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, style="Bg.TFrame")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, bg=COLORS["bg"], highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.content = ttk.Frame(self.canvas, style="Bg.TFrame")
        self._window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", self._region, add="+")
        self.canvas.bind("<Configure>", self._width, add="+")
        self._top = self.winfo_toplevel()
        self._bindings = [(seq, self._top.bind(seq, self._wheel, add="+"))
                          for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>")]
        self.bind("<Destroy>", self._cleanup, add="+")

    def _region(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _width(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)

    def _wheel(self, event):
        target = getattr(event, "widget", None)
        while target is not None and target is not self:
            target = getattr(target, "master", None)
        if target is None:
            return None
        number = getattr(event, "num", None)
        units = -1 if number == 4 else 1 if number == 5 else mousewheel_units(event)
        if units:
            first, last = self.canvas.yview()
            if last - first < 0.9999:
                self.canvas.yview_scroll(units, "units")
        return "break"

    def _cleanup(self, event):
        if event.widget is self:
            for sequence, binding in self._bindings:
                if binding:
                    self._top.unbind(sequence, binding)
            self._bindings = []

