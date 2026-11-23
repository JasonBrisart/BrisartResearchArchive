"""
File: run.py

Purpose
-------
Launch the Brisart Research Archive: the GUI by default, the command line
with --cli, or the automated test suite with --test.

Communication / relationships
-----------------------------
- Calls gui/main_window.main() for the GUI.
- Forwards everything after --cli to cli.main().
- --test discovers and runs tests/test_*.py with unittest; the suites set
  their own temporary APPDATA, so real settings and sessions are never
  touched.

Settings / parameters
---------------------
- python run.py            GUI
- python run.py --cli ...  command line (same arguments as cli.py)
- python run.py --test     every automated test; exit status 0 on success,
  1 on any failure or error

Edge cases
----------
- The GUI is imported only when requested, so the command line and the
  tests work on Python builds without Tk.
- Only the first argument is examined: --cli or --test must come first.

Known limitations
-----------------
- Run it as a script so its folder is first on sys.path.
- --test runs the whole suite; to run one file use
  python -m unittest discover -s tests -p "test_tfl.py".

Examples
--------
- python run.py
- python run.py --cli run
- python run.py --test
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run_tests() -> int:
    import unittest
    tests = str(ROOT / "tests")
    suite = unittest.defaultTestLoader.discover(tests, pattern="test_*.py", top_level_dir=tests)
    return 0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--cli":
        from cli import main as cli_main
        return cli_main(argv[1:])
    if argv and argv[0] == "--test":
        return run_tests()
    from gui.main_window import main as launch_gui
    launch_gui()
    return 0


if __name__ == "__main__":
    sys.exit(main())
