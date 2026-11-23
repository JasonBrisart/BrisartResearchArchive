"""
File: gui/theme.py

Purpose
-------
Define the visual theme: APP_NAME, APP_VERSION, the COLORS palette,
font constants, and apply_theme(), which configures every ttk style the
GUI and the TFL screens use.

Communication / relationships
-----------------------------
- Imported by gui/main_window.py, gui/components/, gui/pages/, and the
  frameworks/TFL/gui_*.py screens.
- APP_VERSION comes from version.py and is shown on the Settings page.

Settings / parameters
---------------------
- COLORS: bg, panel, panel2, panel3, text, muted, border, accent,
  accent2, success, warning, danger.
- FONT Segoe UI 10; FONT_SMALL 9; FONT_TITLE 20 bold; FONT_HEAD 13 bold;
  FONT_MONO Consolas 10.
- ttk base theme: "clam".

Edge cases
----------
- If "clam" is unavailable, the platform default theme is kept.

Known limitations
-----------------
- Only the dark palette exists.
- Segoe UI and Consolas are Windows fonts; other systems substitute.

Examples
--------
- apply_theme(root)
- COLORS["accent"]
"""
import tkinter as tk
from tkinter import ttk

from version import DISPLAY_VERSION

APP_NAME = "Brisart Research Archive"
APP_VERSION = DISPLAY_VERSION
COLORS = {
    "bg": "#070b14",
    "panel": "#0c1320",
    "panel2": "#101827",
    "panel3": "#162235",
    "text": "#eef4fb",
    "muted": "#8a96aa",
    "border": "#223047",
    "accent": "#14b8a6",
    "accent2": "#2dd4bf",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "danger": "#ef4444",
}
FONT = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_HEAD = ("Segoe UI", 13, "bold")
FONT_MONO = ("Consolas", 10)


def apply_theme(root: tk.Tk):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("Bg.TFrame", background=COLORS["bg"])
    style.configure("Side.TFrame", background="#050812")
    style.configure("Top.TFrame", background=COLORS["panel"])
    style.configure("Card.TFrame", background=COLORS["panel"], relief="flat")
    style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=FONT)
    style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=FONT_SMALL)
    style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=FONT_TITLE)
    style.configure("Card.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=FONT)
    style.configure("CardMuted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=FONT_SMALL)
    style.configure("CardTitle.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=FONT_HEAD)
    style.configure(
        "TButton", background=COLORS["panel2"], foreground=COLORS["text"],
        padding=(12, 8), bordercolor=COLORS["border"], font=FONT,
    )
    style.map(
        "TButton",
        background=[("active", COLORS["panel3"]), ("pressed", COLORS["accent"]), ("disabled", COLORS["panel"])],
        foreground=[("disabled", COLORS["muted"])],
    )
    style.configure(
        "Accent.TButton", background=COLORS["accent"], foreground="#031514",
        padding=(12, 8), font=("Segoe UI", 10, "bold"),
    )
    style.map(
        "Accent.TButton",
        background=[("active", COLORS["accent2"]), ("pressed", COLORS["accent"]), ("disabled", COLORS["panel"])],
        foreground=[("disabled", COLORS["muted"])],
    )
    style.configure("TCombobox", fieldbackground=COLORS["panel2"], foreground=COLORS["text"])
    style.configure("TEntry", fieldbackground=COLORS["panel2"], foreground=COLORS["text"])
    style.configure("TCheckbutton", background=COLORS["panel"], foreground=COLORS["text"], font=FONT)
    style.map(
        "TCheckbutton",
        background=[("active", COLORS["panel"]), ("pressed", COLORS["panel"])],
        foreground=[("active", COLORS["text"]), ("pressed", COLORS["text"])],
    )

