"""
File: run.py

Purpose
-------
Start Entitle. This is only the entry point: cli.py beside it does the work. python run.py with
  no arguments opens the desktop window, and python run.py <command> runs that command, so one
  file starts both interfaces. It was main.py before 0.6.0; run.py is the name every Brisart
  tool uses for its entry point.

Communication / relationships
-----------------------------
Imports cli (main) and calls it when run as a script. Python puts this file's folder on the
  import path when it runs, which is how cli, version, entitle/ and gui/ resolve from any
  working folder.

Settings / parameters
---------------------
Takes the command-line arguments documented in cli.py; python run.py --help lists them. With
  no arguments it opens the window.

Edge cases
----------
Importing run does nothing; only running it as a script starts the program. The exit status
  is the one cli.main returns. Run with no arguments (which is also what double-clicking run.py
  does on Windows when .py files are associated with Python) it opens the window. If it cannot,
  it prints the usage and the reason and exits 1; from a double-click that console closes at
  once, so start it from a terminal to read the message.

Known limitations
-----------------
Importing run from another script requires that script to put this folder on sys.path first.
  The window needs tkinter and a display; every command-line command needs neither.

Examples
--------
From the directory containing run.py (or with its full path from anywhere):

    python run.py
    python run.py --help
    python run.py verify --issuer Issuer --subject Lab --product Demo --master-key "..." ^
        --file lab.entitle
    python run.py gui
"""

from cli import main

if __name__ == "__main__":
    raise SystemExit(main())
