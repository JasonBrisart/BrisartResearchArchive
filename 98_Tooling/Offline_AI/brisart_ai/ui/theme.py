"""
File: brisart_ai/ui/theme.py

Purpose
-------
Define workspace colors, typography and spacing.

This desktop presentation component defines the constants and module-level declarations. Its
scope is deliberately limited to the responsibilities visible in this file rather than
duplicating the application-wide workflow. Callers use these declarations through the module
interface; the file is not a separate service or background daemon unless explicitly stated
above.

Communication / relationships
-----------------------------
Presentation modules import constants without initializing Tk.

The direct in-project imports visible in this module are the standard library and its direct
caller. Public entry points are represented by its module-level declarations; this identifies
where behavior is invoked without implying a separate hidden dependency. Higher-level
coordination remains with the calling layer rather than being introduced here.

Settings / parameters
---------------------
Dark mineral surfaces and muted mint accents.

Parameters and configuration are supplied at the entry points named above or by the constants
already declared in this file. This documentation pass does not introduce a new configuration
key, command option, or persisted value. The relevant limits and defaults are those enforced
by the executable code, not assumptions about future integrations.

Edge cases
----------
Tk may substitute missing fonts.

The behaviors documented above must be read together with the actual branches in theme.py; a
caller must not infer success from an empty, rejected, or unsupported result. Error handling,
input validation, and early returns remain the responsibility of the concrete functions in
this module. No additional fallback is created by this documentation.

Known limitations
-----------------
Does not control all dialog or operating system chrome.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Any broader behavior
depends on the documented upstream inputs and downstream consumers. No compatibility adapter
or speculative extension point has been added as part of this pass.

Examples
--------
theme.FG_ACCENT

For a concrete entry point, inspect the constants and module-level declarations; invoke it
through the existing application entry point or its documented caller. The example above is
illustrative of this file's present interface; do not treat it as an instruction to create
additional state or call private functions directly.
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

