#!/usr/bin/env python3
"""
Entitle — single command-line entry point.

Usage:
    python main.py issue    ...    Create a protected entitlement container.
    python main.py verify   ...    Verify a protected entitlement container.
    python main.py track    ...    Record deployments, forks, provenance.
    python main.py revoke   ...    Revoke, reinstate, or check entitlements.
    python main.py report   ...    Audit and report on the record store.
    python main.py gui             Launch the Tkinter GUI.
    python main.py --version       Print the Entitle version and exit.

Run ``python main.py <command> --help`` for a command's own options.

This script bootstraps the sibling ``vendor/`` directory (BrisartSecurityResearch,
used completely unmodified) onto sys.path, then dispatches to the appropriate
``entitle.<command>.main(argv)`` function.

Adding a new CLI command is a matter of adding one entry to COMMAND_MODULES below;
no other part of this file needs to change.
"""
import importlib
import sys

from entitle.bootstrap import ensure_bsr_on_path
from version import __version__

# Maps a CLI command name to the dotted module path implementing it. Each target
# module is expected to expose a ``main(argv=None)`` function, following the same
# convention as entitle.issue, entitle.verify, etc.
COMMAND_MODULES = {
    "issue": "entitle.issue",
    "verify": "entitle.verify",
    "track": "entitle.tracking.cli",
    "revoke": "entitle.revoke",
    "report": "entitle.report",
}


def _print_top_level_help():
    print(__doc__)


def main(argv=None):
    ensure_bsr_on_path()
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _print_top_level_help()
        return 0
    if argv[0] in ("-V", "--version"):
        print(f"Entitle {__version__}")
        return 0

    command, rest = argv[0], argv[1:]
    if command == "gui":
        from gui.app import launch
        launch()
        return 0
    if command not in COMMAND_MODULES:
        print(f"Unknown command: {command!r}")
        print()
        _print_top_level_help()
        return 2
    module = importlib.import_module(COMMAND_MODULES[command])
    return module.main(rest)


if __name__ == "__main__":
    raise SystemExit(main())
