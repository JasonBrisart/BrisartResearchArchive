"""
File: gui/components/scroll_frame.py

Purpose
-------
Provide a vertically scrollable content frame with a visible scrollbar.

Communication / relationships
-----------------------------
Used by the TFL options screen; wheel bindings belong to its Toplevel.

Settings / parameters
---------------------
ScrollFrame(parent) exposes content and canvas; uses the Archive palette.

Edge cases
----------
Wheel events are accepted only from descendants. Destroy removes only
this instance's bindings, leaving other window handlers intact.

Known limitations
-----------------
Touchpad support depends on wheel events delivered by the local Tk build.

Examples
--------
view = ScrollFrame(parent); view.pack(fill="both", expand=True)
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
