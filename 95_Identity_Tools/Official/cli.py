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
    python cli.py encryption archive create backup.bsa docs/ --keyfile k.key
    python cli.py gui
    python cli.py version

Each tool's main() is called in-process with a plain top-level import.

The encryption tool is BSR2's own command-line toolkit
(``brisart_security_cli`` in 97_Encryption/Official), run through the link in
crypto/encryption.py rather than reimplemented: key files, file encryption
(BSR-STREAM-1), sealed messages, hashing, Brisart Secure Archives with
recovery records, split and join, a KDF benchmark, and a self-test. Identity
Tools adds nothing to it, so its commands and output are exactly upstream's.

Communication / relationships
-----------------------------
Depends on (project modules):
- version (version.py)
- crypto.encryption (crypto/encryption.py) -- link status for version, and
  the linked toolkit for the encryption tool
- app (app.py) -- the root-level GUI shell, imported only by the gui command
- biometrics.app (biometrics/app.py)
- vault.app (vault/app.py)
- packages.main (packages/main.py)
Standard library: sys.
Imported by: no other module in this tree imports it directly (it is an entry
point).
Covered by tests: tests/test_cli_dispatcher.py.

Settings / parameters
---------------------
- USAGE -- Help text printed by help, --help and -h (to stdout) and, with exit
  status 2, when no tool or an unknown tool is given (to stderr). It lists
  biometrics, vault, package, encryption, gui, version, and help.
- _DISPATCH -- Maps the first command-line word to its handler: biometrics,
  vault, package, encryption, gui, version, and help, plus the aliases --help
  and -h, which both run help.

Edge cases
----------
- Run as a script, the process exit status is main()'s return value (via
  ``raise SystemExit(main())``).
- biometrics, vault, and package return the tool's own exit status unchanged:
  0 on success, 1 for a negative result (for example a biometrics verify that
  does not match), 2 for an error the tool reports, and 3 when the command
  needs encryption and BSR2 is not linked.
- encryption returns 3 with "Encryption not found: ..." on stderr when BSR2 is not linked; otherwise it returns the toolkit's status (0
  success, 1 for an error it reports, 2 for a usage error).
- version always returns 0 and prints the encryption link on its second line:
  the linked BSR2 release and its folder relative to the
  archive ("..., from 97_Encryption/Official"), or "Encryption not found: ..."
  with the reason. It never prints the archive's absolute location.
- main(): catches SystemExit and handles it in place; it does not propagate to
  the caller.

Known limitations
-----------------
- The gui command imports the root-level ``app`` module (app.py), the same
  shell that ``python app.py`` runs. It therefore needs tkinter and a graphical
  display, exactly like launching app.py directly.
- ``app`` is a generic top-level module name: the gui command relies on the
  repository root being first on sys.path (true when cli.py is run as a script
  or imported by tests/run_tests.py), so an unrelated ``app`` module earlier on
  sys.path would be imported instead.
- Tool modules are imported lazily so `version`/`help` never pay an import cost
  for a tool they are not running.

Examples
--------
::

    python cli.py help
    python cli.py version
    python cli.py vault --vault v.json init
    python cli.py package demo
    python cli.py encryption selftest
    python cli.py encryption keygen backup.key
    python cli.py biometrics --help
    python cli.py gui
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
  encryption [args...]   BSR2 toolkit: keys, files, archives
  gui                    Launch the desktop GUI (Tkinter)
  version                Print the version and the encryption link
  help                   Show this message
"""


def _run_biometrics(rest):
    from biometrics import app
    sys.argv = ["brisart-biometrics", *rest]
    return app.main()


def _run_vault(rest):
    from vault import app
    sys.argv = ["brisart-vault", *rest]
    return app.main()


def _run_package(rest):
    from packages import main as package_main
    sys.argv = ["brisart-package", *rest]
    return package_main.main()


def _run_encryption(rest):
    from crypto import encryption
    from crypto.errors import EncryptionNotFoundError
    try:
        bsr2 = encryption.require()
    except EncryptionNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 3
    return bsr2.cli.main(rest)


def _run_gui(_rest):
    # The GUI shell lives at the repository root (app.py), not in gui/app.py.
    import app as gui_shell
    gui_shell.main()
    return 0


def _run_version(_rest):
    from crypto import encryption
    print(f"BrisartIdentityTools {__version__}")
    print(encryption.status().describe())
    return 0


def _run_help(_rest):
    print(USAGE)
    return 0


_DISPATCH = {
    "biometrics": _run_biometrics,
    "vault": _run_vault,
    "package": _run_package,
    "encryption": _run_encryption,
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
