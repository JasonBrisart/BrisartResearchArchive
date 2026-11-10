"""
File: run.py

Purpose
-------
Start Project Context Helper, a Brisart Research Archive tool that packages a project folder
  into a readable context file, manifest, summary, settings record, and optional ZIP. With a
  project folder argument it exports from the command line; without one it opens the desktop
  window. This file is only the entry point; cli.py beside it does the work.

Communication / relationships
-----------------------------
Imports cli (main) and calls it when run as a script. Python puts this file's folder on the
  import path when it is run, which is how cli, app, storage, export/, and gui/ resolve from
  any working folder.

Application layout (dependencies point down; nothing imports anything above itself):
  run.py              entry point
  cli.py, gui/        interfaces: command line and desktop window
  storage.py          everything remembered between runs
  export/             the engine: settings -> scan, git_state -> render -> pipeline (+ events)
  app.py              identity and every file name the app writes

Settings / parameters
---------------------
Takes the command-line arguments documented in cli.py; python run.py --help lists them.

Edge cases
----------
Importing run.py does nothing; only running it as a script starts the program.

Known limitations
-----------------
Importing run.py from another script requires that script to put this folder on sys.path
  first. The desktop window needs tkinter and a display; command-line exports need neither.

Examples
--------
From the directory containing run.py (or with its full path from anywhere):

    python run.py
    python run.py "/path/to/project"
    python run.py --help
"""

from cli import main

if __name__ == "__main__":
    main()
