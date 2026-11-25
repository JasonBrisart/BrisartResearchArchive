r"""
File: brisart_ai/ui/theme.py

Purpose
-------
Own the desktop palette, typography and spacing constants.

Communication / relationships
-----------------------------
Imported by Tk presentation modules; does not initialize Tk.

No direct project import appears in this module’s top-level imports. The file is reached
as a launcher, test, or helper, or through a runtime import rather than through an
ordinary domain import.

Settings / parameters
---------------------
Constants are applied at startup; the window theme is not a saved preference.

Module configuration and named constants: BG_APP='#1b1e23', BG_PANEL='#20242b',
BG_SIDEBAR='#181b20', BG_INPUT='#262b33', BG_CHAT='#15171b', FG_TEXT='#e6e6e6',
FG_MUTED='#a8b1bd', FG_ACCENT='#4fc3f7', FG_ACCENT_DIM='#2d8cb3', FG_SUCCESS='#7bd88f',
FG_WARN='#f2c94c', FG_USER='#9ad1ff', FG_ASSISTANT='#c9f2d8', FG_SYSTEM='#8a919b',
BORDER='#2c313a', FONT_UI (tuple, 2 entries), FONT_UI_BOLD (tuple, 3 entries),
FONT_HEADING (tuple, 3 entries), and 5 more constants.

Edge cases
----------
The host may substitute unavailable font families.

No explicit exception-handling branch is defined at module level. Unexpected errors
therefore follow the caller’s normal error boundary unless a lower-level helper handles
them.

Known limitations
-----------------
The constants do not determine platform widget rendering by themselves.

Tk style names and available fonts depend on the host theme and operating system. This module does not measure contrast or guarantee identical rendering across platforms.

Examples
--------
theme.SIDEBAR_WIDTH
"""

from __future__ import annotations

BG_APP = "#1b1e23"
BG_PANEL = "#20242b"
BG_SIDEBAR = "#181b20"
BG_INPUT = "#262b33"
BG_CHAT = "#15171b"

FG_TEXT = "#e6e6e6"
FG_MUTED = "#a8b1bd"
FG_ACCENT = "#4fc3f7"
FG_ACCENT_DIM = "#2d8cb3"
FG_SUCCESS = "#7bd88f"
FG_WARN = "#f2c94c"

FG_USER = "#9ad1ff"
FG_ASSISTANT = "#c9f2d8"
FG_SYSTEM = "#8a919b"

BORDER = "#2c313a"

FONT_UI = ("Segoe UI", 10)
FONT_UI_BOLD = ("Segoe UI", 10, "bold")
FONT_HEADING = ("Segoe UI", 12, "bold")
FONT_MONO = ("Consolas", 10)
FONT_MONO_BOLD = ("Consolas", 10, "bold")

PAD = 8
PAD_SMALL = 4

SIDEBAR_WIDTH = 228
