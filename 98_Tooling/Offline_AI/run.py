r"""
File: run.py

Purpose
-------
Initialize native dependencies and saved state before opening the desktop.

Communication / relationships
-----------------------------
- Calls brisart_ai.native_path.install() first, so the flat brisart_url /
  brisart_json / ... imports used across brisart_ai/ resolve. This must stay
  above every other brisart_ai import.
- Calls brisart_ai.state.migrate_legacy_state() once, which moves an index
  and settings file left beside the program by an older release into the
  per-user folder before the window opens.
- Imports DEFAULT_DB from brisart_ai.knowledge.index, the SQLite index path
  inside that per-user folder.
- Calls brisart_ai.ui.app.run(DEFAULT_DB). Constructing the backend service,
  opening the Tk window and handling startup failures all live in
  ui/app.py's run(), not here.

Settings / parameters
---------------------
None of its own. run() takes an optional db_path; this file passes
DEFAULT_DB explicitly. BRISART_NATIVE_API and BRISARTAI_STATE_DIR are read
by native_path and state.

Edge cases
----------
- If the native stack cannot be found, native_path.install() raises
  ImportError listing every location searched, before any window opens.
- A failed move of old saved state prints a warning to stderr and leaves the
  old files where they are; the program still starts.
- A startup failure after that (index locked by another copy, unwritable
  state folder) is handled inside ui/app.py's run() with a dialog, so this
  file has no try/except.
- The `if __name__ == "__main__":` guard keeps an import of this module
  from opening the GUI or moving files; the native_path call still runs on
  import.

Known limitations
-----------------
- Needs a working Tk display. Without one, use cli.py.

Examples
--------
::

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
