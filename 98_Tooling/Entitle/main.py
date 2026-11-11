"""
File: main.py

Purpose
-------
Start Entitle. This is only the entry point: cli.py beside it parses the command line and
  opens the window when asked, so python main.py <command> is the one way in.

Communication / relationships
-----------------------------
Imports cli (main) and calls it when run as a script. Python puts this file's folder on the
  import path when it runs, which is how cli, version, entitle/ and gui/ resolve from any
  working folder.

Settings / parameters
---------------------
Takes the command-line arguments documented in cli.py; python main.py --help lists them.

Edge cases
----------
Importing main does nothing; only running it as a script starts the program. The exit status
  is the one cli.main returns.

Known limitations
-----------------
Importing main from another script requires that script to put this folder on sys.path first.
  The window command needs tkinter and a display; every other command needs neither.

Examples
--------
From the directory containing main.py (or with its full path from anywhere):

    python main.py --help
    python main.py verify --issuer Issuer --subject Lab --product Demo --master-key "..." ^
        --file lab.entitle
    python main.py gui
"""

from cli import main

if __name__ == "__main__":
    raise SystemExit(main())
