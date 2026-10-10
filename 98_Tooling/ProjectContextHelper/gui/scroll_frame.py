"""
File: gui/scroll_frame.py

Purpose
-------
Create a reusable vertically scrollable tkinter content frame for Options and Extras.

Implemented responsibilities:
- create_scrollable_area: Create a canvas, vertical scrollbar, and embedded content frame; wire
  resize/scroll callbacks and return the content frame for callers to populate.
- on_content_configure: Update the canvas scrollregion from its current item bounding box after
  content geometry changes.
- on_canvas_configure: Resize the embedded content window to match the canvas event width.
- on_mousewheel: Convert MouseWheel delta to integer scroll units using delta/120 and scroll the
  canvas vertically.
- on_mousewheel_linux_up: Scroll the canvas upward by one unit for Button-4 events.
- on_mousewheel_linux_down: Scroll the canvas downward by one unit for Button-5 events.
- bind_wheel: Install global MouseWheel/Button-4/Button-5 handlers when the pointer enters the
  canvas.
- unbind_wheel: Remove the global wheel bindings when the pointer leaves the canvas.

Communication / relationships
-----------------------------
Internal imports and exchanged symbols:
This file imports no other application modules; its implementation uses the standard library.

Consumers in the supplied source:
- gui/extras_tab.py imports create_scrollable_area.
- gui/options_tab.py imports create_scrollable_area.

Settings / parameters
---------------------
Receives a parent frame and returns the content frame. Canvas size/configure events synchronize
  content width and scroll region.

Function signatures (nested callbacks are scoped to their enclosing function):
- create_scrollable_area(parent: tk.Frame) -> tk.Frame
- on_content_configure(_event=None) -> None
- on_canvas_configure(event) -> None
- on_mousewheel(event) -> None
- on_mousewheel_linux_up(_event) -> None
- on_mousewheel_linux_down(_event) -> None
- bind_wheel(_event=None) -> None
- unbind_wheel(_event=None) -> None

Edge cases
----------
Mouse-wheel bindings are installed on canvas entry and removed on exit. Handles MouseWheel and
  Linux Button-4/Button-5 events.

A MouseWheel delta smaller than 120 can truncate to zero scroll units. Global wheel handlers are
  installed/removed on canvas enter/leave, not per child widget.

Known limitations
-----------------
Uses global bind_all/unbind_all, which can affect other widgets. MouseWheel delta scaling
  assumes 120-unit steps and is not tuned for every platform/device.

unbind_all removes all handlers for the event sequence, not only this component's callback.
  Multiple scrollable components can interfere with each other's global bindings.

Examples
--------
Usage from the directory containing run.py:

    import tkinter as tk
    from gui.scroll_frame import create_scrollable_area

    window = tk.Tk()
    content = create_scrollable_area(window)
    for index in range(30):
        tk.Label(content, text=f"Export option {index}").pack(anchor="w")
    window.mainloop()
"""

import tkinter as tk


def create_scrollable_area(parent: tk.Frame) -> tk.Frame:
    container = tk.Frame(parent)
    container.pack(fill="both", expand=True)

    canvas = tk.Canvas(container, highlightthickness=0, borderwidth=0)
    scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)

    content = tk.Frame(canvas)
    content_window_id = canvas.create_window((0, 0), window=content, anchor="nw")

    def on_content_configure(_event=None) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))

    def on_canvas_configure(event) -> None:
        canvas.itemconfig(content_window_id, width=event.width)

    content.bind("<Configure>", on_content_configure)
    canvas.bind("<Configure>", on_canvas_configure)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    def on_mousewheel(event) -> None:
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def on_mousewheel_linux_up(_event) -> None:
        canvas.yview_scroll(-1, "units")

    def on_mousewheel_linux_down(_event) -> None:
        canvas.yview_scroll(1, "units")

    def bind_wheel(_event=None) -> None:
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        canvas.bind_all("<Button-4>", on_mousewheel_linux_up)
        canvas.bind_all("<Button-5>", on_mousewheel_linux_down)

    def unbind_wheel(_event=None) -> None:
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")

    canvas.bind("<Enter>", bind_wheel)
    canvas.bind("<Leave>", unbind_wheel)

    return content

