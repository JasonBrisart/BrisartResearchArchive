"""
File: tools/integrity_checkpoint.py

Purpose
-------
Standalone CLI for common.integrity_ledger. Meant to be invoked either by hand
(before/after a sensitive operation on a vault.json, a biometrics keyring.json,
or a package's .json file) or by an OS-level scheduler (a cron job, a Windows
Scheduled Task) so checkpoints are recorded at a regular cadence with no
persistent background process and no third-party scheduling dependency --
consistent with tools/envinfo.py's existing standalone-script pattern in this
repository.

Public interface:
- class AppError(ValueError) -- Raised for user-facing CLI failures.
- command_checkpoint(args)
- command_status(args)
- command_history(args)
- command_verify(args)
- command_list_tracked(args)
- build_parser()
- main(argv=None)

Design notes:

Read common/integrity_ledger.py's module docstring before relying on this for
anything real: checkpointing narrows, but cannot close, the "edit then revert
before the next check" blind spot every tamper- evidence mechanism in this
project shares. The smaller the gap between scheduled checkpoints, the smaller
that blind spot -- but it is never zero unless checkpoints are continuous,
which this tool does not attempt to be.

Communication / relationships
-----------------------------
Depends on (project modules):
- common.integrity_ledger (common/integrity_ledger.py)
Standard library: argparse, pathlib, sys.
Imported by: no other module in this tree imports it directly (it is an entry
point).
Covered by tests: no test file imports this module directly.

Settings / parameters
---------------------
- DEFAULT_LEDGER_PATH = Path("data") / "integrity" / "ledger.json"

Options shared by every command:
- --ledger: path to the ledger file (default: data/integrity/ledger.json).

Commands (each takes the options listed under it):
- checkpoint -- record a new checkpoint of a file.
  - target_file (positional).
  - --label: optional actor label to record with this checkpoint.
- status -- compare a file's current hash against its latest checkpoint.
  - target_file (positional).
- history -- list every checkpoint recorded for a file.
  - target_file (positional).
- verify -- verify the ledger's own hash chain is intact.
  - no options of its own.
- list-tracked -- list every file path tracked in the ledger.
  - no options of its own.

Edge cases
----------
- command_checkpoint() raises AppError.
- command_verify() raises AppError.
- Run as a script, the process exit status is main()'s return value (via
  ``raise SystemExit(main())``).
- command_checkpoint(), command_verify(): translates
  integrity_ledger.IntegrityLedgerError into AppError; other exceptions may still propagate.
- main(): catches AppError and handles it in place; it does not propagate to
  the caller.

Known limitations
-----------------
- Tracked in docs/KNOWN_ISSUES.md: KI-004: Integrity checkpoints have
  observation gaps and unkeyed-history limitations.
- Run it as a module from the repository root (``python -m
  tools.integrity_checkpoint``). Running the file directly (``python
  tools/integrity_checkpoint.py``) fails with ModuleNotFoundError because the
  repository root is not on sys.path.
- ``status`` exits 0 even when the file no longer matches its latest
  checkpoint; read the printed result rather than the exit status.
- No test module imports this file directly; as an entry point it is verified
  only by running it, so check changes manually.

Examples
--------
::

    python -m tools.integrity_checkpoint --help
    python -m tools.integrity_checkpoint checkpoint --help
    python -m tools.integrity_checkpoint status --help
    python -m tools.integrity_checkpoint history --help
"""

import argparse
import sys
from pathlib import Path

from common import integrity_ledger

DEFAULT_LEDGER_PATH = Path("data") / "integrity" / "ledger.json"


class AppError(ValueError):
    """Raised for user-facing CLI failures."""


def _ledger_path(args) -> Path:
    return Path(args.ledger) if args.ledger else DEFAULT_LEDGER_PATH


def command_checkpoint(args) -> int:
    ledger_path = _ledger_path(args)
    try:
        entry = integrity_ledger.append_checkpoint(ledger_path, args.target_file, actor_label=args.label)
    except integrity_ledger.IntegrityLedgerError as exc:
        raise AppError(str(exc)) from exc
    print(f"checkpoint recorded for {entry['target_path']}")
    print(f"  sha256:      {entry['sha256']}")
    print(f"  size_bytes:  {entry['size_bytes']}")
    print(f"  recorded_at: {entry['recorded_at']}")
    print(f"  ledger:      {ledger_path}")
    return 0


def command_status(args) -> int:
    ledger_path = _ledger_path(args)
    status = integrity_ledger.current_status(ledger_path, args.target_file)
    print(f"target:           {status['target_path']}")
    if status["current_sha256"] is None:
        print("current state:    file does not exist")
    else:
        print(f"current sha256:   {status['current_sha256']}")
    if status["latest_checkpoint"] is None:
        print("latest checkpoint: none recorded yet")
        print("result:           UNKNOWN (no prior checkpoint to compare against)")
        return 0
    checkpoint = status["latest_checkpoint"]
    print(f"latest checkpoint: {checkpoint['recorded_at']} (sha256 {checkpoint['sha256']})")
    if status["matches_latest_checkpoint"]:
        print("result:           MATCHES latest checkpoint")
        return 0
    print("result:           DOES NOT MATCH latest checkpoint")
    return 1


def command_history(args) -> int:
    ledger_path = _ledger_path(args)
    entries = integrity_ledger.history_for_path(ledger_path, args.target_file)
    if not entries:
        print(f"no checkpoints recorded for {args.target_file}.")
        return 0
    for entry in entries:
        label = f" ({entry['actor_label']})" if entry.get("actor_label") else ""
        print(f"{entry['recorded_at']}  sha256={entry['sha256']}  size={entry['size_bytes']}{label}")
    return 0


def command_verify(args) -> int:
    ledger_path = _ledger_path(args)
    try:
        integrity_ledger.verify_ledger(ledger_path)
    except integrity_ledger.IntegrityLedgerError as exc:
        raise AppError(str(exc)) from exc
    entry_count = len(integrity_ledger.all_entries(ledger_path))
    print(f"ledger verified: {entry_count} entries, chain intact.")
    return 0


def command_list_tracked(args) -> int:
    ledger_path = _ledger_path(args)
    paths = integrity_ledger.list_tracked_paths(ledger_path)
    if not paths:
        print("no files are currently tracked in this ledger.")
        return 0
    for path in paths:
        print(path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="integrity-checkpoint",
        description=(
            "Record and inspect periodic file checkpoints, external to the "
            "files themselves, to narrow (not close) the edit-then-revert "
            "blind spot every tamper-evidence mechanism in this project shares."
        ),
    )
    parser.add_argument(
        "--ledger", default=None,
        help=f"path to the ledger file (default: {DEFAULT_LEDGER_PATH}).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    checkpoint = subparsers.add_parser("checkpoint", help="record a new checkpoint of a file.")
    checkpoint.add_argument("target_file")
    checkpoint.add_argument("--label", default="", help="optional actor label to record with this checkpoint.")
    checkpoint.set_defaults(handler=command_checkpoint)

    status = subparsers.add_parser("status", help="compare a file's current hash against its latest checkpoint.")
    status.add_argument("target_file")
    status.set_defaults(handler=command_status)

    history = subparsers.add_parser("history", help="list every checkpoint recorded for a file.")
    history.add_argument("target_file")
    history.set_defaults(handler=command_history)

    verify = subparsers.add_parser("verify", help="verify the ledger's own hash chain is intact.")
    verify.set_defaults(handler=command_verify)

    list_tracked = subparsers.add_parser("list-tracked", help="list every file path tracked in the ledger.")
    list_tracked.set_defaults(handler=command_list_tracked)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    try:
        return args.handler(args)
    except AppError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())




