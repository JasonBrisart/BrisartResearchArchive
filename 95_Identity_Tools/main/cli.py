"""
File: cli.py

Purpose
-------
Unified entry point: python cli.py <tool> ...

Public interface:
- main(argv=None)

Design notes:

    python cli.py biometrics enroll ...
    python cli.py vault --vault v.json init
    python cli.py package demo
    python cli.py gui
    python cli.py version

Everything now lives flat at the repo root (no wrapper package), so each tool's
main() is called in-process with a plain top-level import.

Communication / relationships
-----------------------------
Depends on (project modules):
- version (version.py)
- biometrics.app (biometrics/app.py)
- vault.app (vault/app.py)
- packages.main (packages/main.py)
Standard library: sys.
Imported by: no other module in this tree imports it directly (it is an entry
point).
Covered by tests: tests/test_cli_dispatcher.py.

Settings / parameters
---------------------
- USAGE = multi-line text template (410 chars)
- _DISPATCH = dict of 8 entries

Edge cases
----------
- Run as a script, the process exit status is main()'s return value (via
  ``raise SystemExit(main())``).
- main(): catches SystemExit and handles it in place; it does not propagate to
  the caller.

Known limitations
-----------------
- The gui command imports ``gui.app``, which does not exist in this tree (the
  GUI shell currently lives at the repository-root app.py), so ``python cli.py
  gui`` raises ImportError until that file is moved to gui/app.py.
- Tool modules are imported lazily so `version`/`help` never pay an import cost
  for a tool they are not running.

Examples
--------
::

    python cli.py help
    python cli.py version
    python cli.py vault --vault v.json init
    python cli.py package demo
    python cli.py biometrics --help
"""

import sys

from version import __version__

USAGE = """\
brisart - unified entry point for BrisartIdentityTools

Usage:
  python cli.py <tool> [args...]

Tools:
  biometrics [args...]   Local biometric enroll/verify
  vault      [args...]   Encrypted record store
  package    [args...]   Identity-bound packages
  gui                    Launch the desktop GUI (Tkinter)
  version                Print the ecosystem version
  help                   Show this message
"""


def _run_biometrics(rest):
    from biometrics import app
    sys.argv = ["brisart-biometrics", *rest]
    app.main()
    return 0


def _run_vault(rest):
    from vault import app
    sys.argv = ["brisart-vault", *rest]
    app.main()
    return 0


def _run_package(rest):
    from packages import main as package_main
    sys.argv = ["brisart-package", *rest]
    package_main.main()
    return 0


def _run_gui(_rest):
    from gui import app
    app.main()
    return 0


def _run_version(_rest):
    print(f"BrisartIdentityTools {__version__}")
    return 0


def _run_help(_rest):
    print(USAGE)
    return 0


_DISPATCH = {
    "biometrics": _run_biometrics,
    "vault": _run_vault,
    "package": _run_package,
    "gui": _run_gui,
    "version": _run_version,
    "help": _run_help,
    "--help": _run_help,
    "-h": _run_help,
}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(USAGE, file=sys.stderr)
        return 2
    tool, rest = argv[0], argv[1:]
    handler = _DISPATCH.get(tool)
    if handler is None:
        print(f"brisart: unknown tool '{tool}'.\n", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    try:
        return handler(rest)
    except SystemExit as exit_exc:
        return int(exit_exc.code or 0)


if __name__ == "__main__":
    raise SystemExit(main())




