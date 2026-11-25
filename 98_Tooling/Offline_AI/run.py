r"""
File: run.py

Purpose
-------
Start the BrisartAI desktop.

Communication / relationships
-----------------------------
Resolves external APIs and migrates eligible state before starting ui.app.

Direct project imports: brisart_ai, brisart_ai.knowledge.index, brisart_ai.ui.app.

Concrete calls within this file include native_path.install, state.migrate_legacy_state.

Settings / parameters
---------------------
Uses the default database path selected by state.py.

This file has no independently configurable runtime parameters. The values it exports
are consumed by its owner rather than loaded from another settings file.

Edge cases
----------
Startup diagnostics distinguish dependency initialization failure from other launch
errors.

No explicit exception-handling branch is defined at module level. Unexpected errors
therefore follow the caller’s normal error boundary unless a lower-level helper handles
them.

Known limitations
-----------------
Requires Tk and a working display for the desktop.

Examples
--------
python run.py
"""

from __future__ import annotations

from brisart_ai import native_path

native_path.install()

from brisart_ai import state  # noqa: E402
from brisart_ai.knowledge.index import DEFAULT_DB  # noqa: E402
from brisart_ai.ui.app import run  # noqa: E402

if __name__ == "__main__":
    state.migrate_legacy_state()
    run(DEFAULT_DB)
