"""
File: brisart_ai/ui/theme.py

Purpose
-------
Define workspace colors, typography and spacing.

Communication / relationships
-----------------------------
Presentation modules import constants without initializing Tk.

Settings / parameters
---------------------
Dark mineral surfaces and muted mint accents.

Edge cases
----------
Tk may substitute missing fonts.

Known limitations
-----------------
Does not control all dialog or operating system chrome.

Examples
--------
theme.FG_ACCENT
"""

from __future__ import annotations

BG_APP = "#121819"
BG_PANEL = "#1c2526"
BG_SIDEBAR = "#162020"
BG_INPUT = "#263333"
BG_CHAT = "#141c1d"

FG_TEXT = "#e6e6e6"
FG_MUTED = "#a8b1bd"
FG_ACCENT = "#9bd8c0"
FG_ACCENT_DIM = "#73bca4"
FG_SUCCESS = "#7bd88f"
FG_WARN = "#f2c94c"

FG_USER = "#b8e4d7"
FG_ASSISTANT = "#c9f2d8"
FG_SYSTEM = "#8a919b"

BORDER = "#435556"

FONT_UI = ("Segoe UI", 10)
FONT_UI_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 17, "bold")
FONT_HEADING = ("Segoe UI", 12, "bold")
FONT_MONO = ("Consolas", 10)
FONT_MONO_BOLD = ("Consolas", 10, "bold")

PAD = 8
PAD_SMALL = 4

SIDEBAR_WIDTH = 228
