"""
File: main.py

Purpose
-------
Launch the Brisart Research Archive: the GUI by default, or the
command line with --cli.

Communication / relationships
-----------------------------
- Calls gui/main_window.main() for the GUI.
- Forwards everything after --cli to cli.main().

Settings / parameters
---------------------
- python main.py            GUI
- python main.py --cli ...  command line (same arguments as cli.py)

Edge cases
----------
- The GUI is imported only when requested, so the command line works on
  Python builds without Tk.

Known limitations
-----------------
- Run it as a script so its folder is first on sys.path.

Examples
--------
- python main.py
- python main.py --cli run
"""
import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--cli":
        from cli import main as cli_main
        return cli_main(argv[1:])
    from gui.main_window import main as launch_gui
    launch_gui()
    return 0


if __name__ == "__main__":
    sys.exit(main())
