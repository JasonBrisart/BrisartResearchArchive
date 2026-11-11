"""
File: cli.py

Purpose
-------
Be Entitle's command line: parse arguments, call the domain functions in entitle/, print the
  result, and turn expected failures into a one-line error with an exit status. It holds every
  command (issue, verify, migrate, track, revoke, report, gui) so the domain modules contain no
  argument parsing, and the window and the command line share one implementation of each
  operation.

Communication / relationships
-----------------------------
Imports version (the version text), entitle/common.py (EntitleError), entitle/encryption.py
  (status, for --version), entitle/entitlements.py, entitle/records.py (RecordStore,
  ALL_RECORD_TYPES), entitle/report.py, entitle/revoke.py and entitle/tracking.py.
  gui/window.py is imported only by the gui command, so the other commands never load tkinter.
  Importing this file never touches 97_Encryption; only the commands that seal or open an
  entitlement (issue, verify, migrate, track deploy) and --version resolve it. Imported by
  run.py (main) and tests/test_cli.py.

Settings / parameters
---------------------
Commands: issue, verify, migrate, track {deploy, fork, provenance, list}, revoke {revoke,
  reinstate, check}, report, gui. --version prints "Entitle <version>" and a second line naming
  the linked encryption (or "Encryption not found: <reason>"). Every record command requires an
  explicit --store: there is deliberately no default location, so records never land somewhere
  the operator did not choose. track list --type accepts the five record types. report takes
  --format text|json and an optional --output file. issue accepts an optional --drbg-seed and
  --drbg-personalization; neither is needed. --expires takes an ISO timestamp; a date alone means
  00:00 UTC that day. Run run.py <command> --help for each command's flags.

Edge cases
----------
Exit status: 0 on success; 1 for verify when the entitlement is denied and for any expected
  error (invalid key or seed, blank required field, invalid expiry or deployment limit, missing
  or malformed file, a file that migrate cannot open, corrupted or busy record store,
  97_Encryption not found, missing tkinter); 2 for a usage error; 130 when interrupted. Errors
  print as "Error: ..." on stderr with no traceback; an import failure inside the window code
  that is not a missing tkinter is a real defect and is not disguised. Without 97_Encryption the
  commands that need no encryption (report, revoke, track fork, provenance and list) still work.
  verify prints a NOTE after VERIFIED when the file still uses the previous encryption, and
  migrate reports UNCHANGED for a file that already uses the current one. track deploy exits 0
  even when the deployment is refused: the outcome is in the printed JSON ("recorded": false),
  as before. With no command it prints help and exits 0. A report on a store that does not
  exist succeeds and says so. Output never fails once the work is done: characters the console
  or a redirected file cannot encode (for example Cyrillic or Chinese names on a Windows code
  page) are printed as backslash escapes, so a record that was written is never reported as a
  failure that invites a duplicate.

Known limitations
-----------------
--master-key, --drbg-seed and --drbg-personalization are command-line arguments, so they are
  visible in the process list and in shell history; use a throwaway key for testing and a
  controlled shell for real keys. main() reads sys.argv unless an argument list is passed.

Examples
--------
From the directory containing run.py:

    python run.py issue --issuer Issuer --subject Lab --product Demo --entitlement-id lab-001 ^
        --master-key "a-master-key-that-is-at-least-32-bytes-long" --deployment-limit 3 ^
        --output entitlements/lab.entitle
    python run.py verify --issuer Issuer --subject Lab --product Demo --master-key "..." ^
        --file entitlements/lab.entitle
    python run.py migrate --issuer Issuer --subject Lab --product Demo --master-key "..." ^
        --file entitlements/older_lab.entitle
    python run.py track deploy --issuer Issuer --subject Lab --product Demo --master-key "..." ^
        --entitlement entitlements/lab.entitle --host node-1 --store records/entitle_records.log
    python run.py revoke check --entitlement-id lab-001 --store records/entitle_records.log
    python run.py report --store records/entitle_records.log
    python run.py gui

    (Windows line continuation is ^; on Linux and macOS use \\.)
"""

import argparse
import json
import sys
from pathlib import Path

from entitle import encryption, entitlements, revoke, tracking
from entitle.common import EntitleError
from entitle.records import ALL_RECORD_TYPES, RecordStore
from entitle.report import build_report, format_text
from version import __version__

PREVIOUS_ENCRYPTION_NOTE = (
    "NOTE: this file still uses the previous encryption (BSR2 Alpha 3). "
    "Run 'python run.py migrate' to re-seal it with the current encryption."
)


class _VersionAction(argparse.Action):
    """--version: the version, then which BSR2 Entitle is linked to (resolved only when asked)."""

    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        print(f"Entitle {__version__}")
        print(encryption.status().describe())
        parser.exit()


def _make_output_safe():
    """Printing must never fail after the work is done: escape what the output cannot encode."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="backslashreplace")
            except (ValueError, OSError):
                pass


def _print_json(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _cmd_issue(args):
    payload = entitlements.issue_entitlement(
        issuer=args.issuer,
        subject=args.subject,
        product=args.product,
        entitlement_id=args.entitlement_id,
        master_key=args.master_key,
        drbg_seed=args.drbg_seed,
        drbg_personalization=args.drbg_personalization,
        output=args.output,
        expires=args.expires,
        enterprise=args.enterprise,
        modify=args.modify,
        fork=args.fork,
        export_source=args.export_source,
        redistribute=args.redistribute,
        deployment_limit=args.deployment_limit,
        support_tier=args.support_tier,
    )
    print("Protected entitlement created:")
    print(args.output)
    print()
    print("Payload summary:")
    _print_json(payload)
    return 0


def _cmd_verify(args):
    result = entitlements.verify_entitlement(
        issuer=args.issuer,
        subject=args.subject,
        product=args.product,
        master_key=args.master_key,
        path=args.file,
    )
    _print_json(result.to_dict())
    print()
    if result.allowed:
        print("VERIFIED: entitlement is valid.")
        if entitlements.uses_previous_encryption(args.file):
            print(PREVIOUS_ENCRYPTION_NOTE)
        return 0
    print(f"DENIED: {result.reason}")
    return 1


def _cmd_migrate(args):
    outcome = entitlements.migrate_entitlement(
        issuer=args.issuer,
        subject=args.subject,
        product=args.product,
        master_key=args.master_key,
        path=args.file,
    )
    if outcome["migrated"]:
        print(f"MIGRATED: {args.file} now uses the current encryption (BSR2-S64-SIV).")
        print("Entitle versions before 0.5.0 cannot open it; keep a copy if one of them must.")
    else:
        print(f"UNCHANGED: {args.file} already uses the current encryption.")
    return 0


def _cmd_deploy(args):
    outcome = tracking.deploy_from_file(
        issuer=args.issuer,
        subject=args.subject,
        product=args.product,
        master_key=args.master_key,
        entitlement_path=args.entitlement,
        host=args.host,
        store=RecordStore(args.store),
        environment=args.environment,
        notes=args.notes,
    )
    _print_json(outcome)
    return 0


def _cmd_fork(args):
    _print_json(
        tracking.record_fork(
            RecordStore(args.store),
            product=args.product,
            source_version=args.source_version,
            fork_name=args.fork_name,
            maintainer=args.maintainer,
            environment=args.environment,
            notes=args.notes,
        )
    )
    return 0


def _cmd_provenance(args):
    _print_json(
        tracking.record_provenance(
            RecordStore(args.store),
            product=args.product,
            origin=args.origin,
            version=args.version,
            custodian=args.custodian,
            previous_version=args.previous_version,
            notes=args.notes,
        )
    )
    return 0


def _cmd_list(args):
    _print_json(RecordStore(args.store).filter(record_type=args.type))
    return 0


def _cmd_revoke(args):
    _print_json(
        revoke.revoke(
            RecordStore(args.store), args.entitlement_id,
            issuer_id=args.issuer, product_id=args.product, reason=args.reason,
        )
    )
    return 0


def _cmd_reinstate(args):
    _print_json(
        revoke.reinstate(
            RecordStore(args.store), args.entitlement_id,
            issuer_id=args.issuer, product_id=args.product, reason=args.reason,
        )
    )
    return 0


def _cmd_check(args):
    status = revoke.revocation_status(RecordStore(args.store), args.entitlement_id)
    _print_json(status)
    print()
    print("REVOKED" if status["revoked"] else "ACTIVE")
    return 0


def _cmd_report(args):
    report = build_report(RecordStore(args.store))
    rendered = json.dumps(report, indent=2, ensure_ascii=False) if args.format == "json" else format_text(report)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + "\n", encoding="utf-8")
        print(f"Report written to {path}")
    else:
        print(rendered)
    return 0


def _cmd_gui(args):
    try:
        from gui.window import launch
    except ModuleNotFoundError as exc:
        if exc.name not in ("tkinter", "_tkinter"):
            raise
        raise EntitleError("The window needs tkinter, which this Python installation does not provide.") from exc
    launch()
    return 0


def _add_store(parser):
    parser.add_argument("--store", required=True, help="Record store file path.")


def _add_identity(parser, *, required=True):
    parser.add_argument("--issuer", required=required, help="Issuer ID.")
    parser.add_argument("--subject", required=required, help="Customer, lab or organization ID.")
    parser.add_argument("--product", required=required, help="Product ID.")


def _add_drbg(parser):
    parser.add_argument("--drbg-seed", default=None, help="Optional extra DRBG seed text (at least 64 bytes).")
    parser.add_argument(
        "--drbg-personalization", default=None, help="Optional DRBG personalization text (at least 16 bytes)."
    )


def build_parser():
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="Entitle: offline software rights management with a tamper-evident record log.",
    )
    parser.add_argument("-V", "--version", action=_VersionAction, help="Show the version and the linked encryption.")
    commands = parser.add_subparsers(dest="command", metavar="command")

    issue = commands.add_parser("issue", help="Create a protected entitlement container.")
    _add_identity(issue)
    issue.add_argument("--entitlement-id", required=True, help="Entitlement ID.")
    issue.add_argument(
        "--expires", default=None,
        help="Expiration ISO timestamp, for example 2027-01-31T23:59:59Z (a date alone means 00:00 UTC that day).",
    )
    issue.add_argument("--output", required=True, help="Output .entitle path.")
    issue.add_argument("--master-key", required=True, help="Master key text (32 to 1024 bytes).")
    _add_drbg(issue)
    issue.add_argument("--enterprise", action="store_true", help="Grant enterprise feature rights.")
    issue.add_argument("--modify", action="store_true", help="Grant private modification rights.")
    issue.add_argument("--fork", action="store_true", help="Grant internal fork rights.")
    issue.add_argument("--export-source", action="store_true", help="Grant source export rights.")
    issue.add_argument("--redistribute", action="store_true", help="Grant redistribution rights.")
    issue.add_argument("--deployment-limit", type=int, default=1, help="Maximum authorized deployments.")
    issue.add_argument("--support-tier", default="standard", help="Support tier label.")
    issue.set_defaults(handler=_cmd_issue)

    verify = commands.add_parser("verify", help="Verify a protected entitlement container.")
    _add_identity(verify)
    verify.add_argument("--master-key", required=True, help="Master key text.")
    verify.add_argument("--file", required=True, help="Protected .entitle file.")
    verify.set_defaults(handler=_cmd_verify)

    migrate = commands.add_parser(
        "migrate", help="Re-seal an entitlement written by an Entitle before 0.5.0 with the current encryption."
    )
    _add_identity(migrate)
    migrate.add_argument("--master-key", required=True, help="Master key text.")
    migrate.add_argument("--file", required=True, help="Protected .entitle file, replaced in place.")
    migrate.set_defaults(handler=_cmd_migrate)

    track = commands.add_parser("track", help="Record deployments, forks and provenance.")
    track_commands = track.add_subparsers(dest="track_command", metavar="action", required=True)

    deploy = track_commands.add_parser("deploy", help="Record a governed deployment.")
    _add_identity(deploy)
    deploy.add_argument("--master-key", required=True)
    deploy.add_argument("--entitlement", required=True, help="Protected .entitle file.")
    deploy.add_argument("--host", required=True, help="Deployment host or node ID.")
    deploy.add_argument("--environment", default=None)
    deploy.add_argument("--notes", default=None)
    _add_store(deploy)
    deploy.set_defaults(handler=_cmd_deploy)

    fork = track_commands.add_parser("fork", help="Record an internal fork.")
    fork.add_argument("--product", required=True)
    fork.add_argument("--source-version", required=True)
    fork.add_argument("--fork-name", required=True)
    fork.add_argument("--maintainer", required=True)
    fork.add_argument("--environment", default=None)
    fork.add_argument("--notes", default=None)
    _add_store(fork)
    fork.set_defaults(handler=_cmd_fork)

    provenance = track_commands.add_parser("provenance", help="Record provenance and ownership.")
    provenance.add_argument("--product", required=True)
    provenance.add_argument("--origin", required=True)
    provenance.add_argument("--version", required=True)
    provenance.add_argument("--previous-version", default=None)
    provenance.add_argument("--custodian", required=True)
    provenance.add_argument("--notes", default=None)
    _add_store(provenance)
    provenance.set_defaults(handler=_cmd_provenance)

    listing = track_commands.add_parser("list", help="List records.")
    listing.add_argument("--type", default=None, choices=ALL_RECORD_TYPES, help="Only records of this type.")
    _add_store(listing)
    listing.set_defaults(handler=_cmd_list)

    revoke_group = commands.add_parser("revoke", help="Revoke, reinstate or check entitlements.")
    revoke_commands = revoke_group.add_subparsers(dest="revoke_command", metavar="action", required=True)
    for name, handler, help_text in (
        ("revoke", _cmd_revoke, "Record a revocation."),
        ("reinstate", _cmd_reinstate, "Record a reinstatement."),
    ):
        action = revoke_commands.add_parser(name, help=help_text)
        action.add_argument("--entitlement-id", required=True)
        action.add_argument("--issuer", default=None)
        action.add_argument("--product", default=None)
        action.add_argument("--reason", default=None)
        _add_store(action)
        action.set_defaults(handler=handler)
    check = revoke_commands.add_parser("check", help="Check revocation status.")
    check.add_argument("--entitlement-id", required=True)
    _add_store(check)
    check.set_defaults(handler=_cmd_check)

    report = commands.add_parser("report", help="Audit the record store and verify its hash chain.")
    _add_store(report)
    report.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    report.add_argument("--output", default=None, help="Write the report to this file instead of the screen.")
    report.set_defaults(handler=_cmd_report)

    gui = commands.add_parser("gui", help="Open the desktop window.")
    gui.set_defaults(handler=_cmd_gui)
    return parser


def main(argv=None):
    _make_output_safe()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        return args.handler(args)
    except (EntitleError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
