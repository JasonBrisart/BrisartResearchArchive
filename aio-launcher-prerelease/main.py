"""
File: main.py

Purpose:
Launch the Brisart Research Archive GUI.

Communication / relationships:
- Calls gui.main_window.main().

Settings / parameters:
- None.

Edge cases:
- Run it as a script (python main.py) so its folder is first on
  sys.path and the top-level packages import.

Known limitations:
- GUI only; no command-line options.

Examples:
- python main.py
"""
from gui.main_window import main

if __name__ == "__main__":
    main()
    