"""
File: run.py

Purpose
-------
Launch Project Context Helper within Brisart Research Archive through the shared CLI dispatcher;
  no root argument opens the desktop GUI.

The module-level main guard calls the imported cli.cli.main only during direct execution.

Communication / relationships
-----------------------------
Internal imports and exchanged symbols:
- cli.cli: main.

Consumers in the supplied source:
No direct application-module importer is present in the supplied source; entry points/tests may
  be invoked through their execution guards or discovery.

Settings / parameters
---------------------
Reads command-line arguments through cli.cli; inserts its own directory into sys.path before
  importing the dispatcher.

Edge cases
----------
The main guard prevents launch when imported. CLI validation and GUI failures are handled
  downstream.

Importing run.py changes sys.path but does not call main unless __name__ is __main__.

Known limitations
-----------------
Source launch imports tkinter through the CLI even for command-line operations; a Python
  installation with tkinter is needed.

The entry point does not package dependencies or detect an absent graphical display; those
  failures arise during imports/GUI creation.

Examples
--------
Usage from the directory containing run.py:

    python run.py
    python run.py "/path/to/project" --profile archive --no-zip
    python run.py "/path/to/project" --profile standard --remember-settings
    python run.py --list-profiles
    python run.py --help
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cli.cli import main

if __name__ == "__main__":
    main()

