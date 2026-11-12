"""
File: cli.py

Purpose
-------
Be Entitle's command line: parse arguments, call the domain functions in entitle/, print the
  result, and turn expected failures into a one-line error with an exit status. It holds every
  command, so the domain modules contain no argument parsing and the window and the command
  line share one implementation of each operation. Secrets (master key, passphrase) are never
  required on the command line. Run with no command it opens the desktop window, so
  python run.py is the one way in to either interface.

Communication / relationships
-----------------------------
Imports version (the version text) and, from entitle/: common.py (EntitleError), encryption.py
  (status and signature_status, for --version), signing.py (key files), host.py (fingerprint,
  HostState), entitlements.py, records.py (RecordStore, ALL_RECORD_TYPES), report.py,
  revoke.py, revocation_list.py, checkpoints.py and tracking.py. gui/window.py is imported only
  when the window is opened, so the other commands never load tkinter. Importing this file never
  touches 97_Encryption. Imported by run.py (main), tests/test_cli.py and tests/test_gui.py.

Settings / parameters
---------------------
Commands: keys {generate, show}, fingerprint, issue, verify, inspect, migrate, track {deploy,
  release, fork, provenance, list}, revoke {revoke, reinstate, check, publish}, checkpoint
  {create, verify}, report and gui; run.py <command> --help lists each one's options. --version
  prints the version and the linked encryption and signature lines. A signing key's passphrase
  comes from --passphrase-file, the ENTITLE_PASSPHRASE environment variable, or a prompt (asked
  twice by keys generate); there is deliberately no --passphrase. A shared master key comes from
  --master-key-file, ENTITLE_MASTER_KEY, or --master-key (kept for compatibility; visible in the
  process list). Every record command requires an explicit --store. --public-key may be repeated
  to trust several issuer keys. Abbreviated options are not accepted.

Edge cases
----------
Exit status: 0 on success; 1 for verify when denied, checkpoint verify when it fails, and any
  expected error (missing key or passphrase, wrong passphrase, invalid input, a file that exists
  without --force, missing or malformed file, damaged or busy store, 97_Encryption or the
  signature module not found, missing tkinter); 2 for a usage error; 3 (EXIT_REFUSED) only with
  --strict, for a refused deployment, a release of nothing, or a broken chain in report; 130
  when interrupted. Without --strict, track deploy and report exit 0 as before and the outcome
  is in the output. Errors print as "Error: ..." on stderr with no traceback. verify on a
  shared-key file prints a NOTE that it can be converted to signed (and, for a pre-0.5.0 file,
  the migrate note instead). A signed file needs --public-key and a shared-key file the master
  key; the error names which. Without 97_Encryption, report, revoke revoke/reinstate/check and
  track release/fork/provenance/list still work. Output never fails once the work is done:
  characters the console cannot encode are printed as backslash escapes.

Known limitations
-----------------
--master-key and the shared-key --drbg-seed and --drbg-personalization are visible in the
  process list and shell history; prefer the file and environment forms. An environment
  variable is visible to other programs run by the same user. main() reads sys.argv unless an
  argument list is passed.

Examples
--------
From the directory containing run.py (Windows continues a line with ^; Linux and macOS use a
  backslash). Keep the signing key outside the repository, as here:

    python run.py
    python run.py keys generate --name Issuer ^
        --signing-key %USERPROFILE%/EntitleKeys/issuer.signing-key ^
        --public-key keys/issuer.public-key
    python run.py issue --issuer Issuer --subject Lab --product Demo --entitlement-id lab-001 ^
        --signing-key %USERPROFILE%/EntitleKeys/issuer.signing-key --deployment-limit 3 ^
        --output entitlements/lab.entitle
    python run.py verify --issuer Issuer --subject Lab --product Demo ^
        --public-key keys/issuer.public-key --file entitlements/lab.entitle
    python run.py track deploy --issuer Issuer --subject Lab --product Demo ^
        --public-key keys/issuer.public-key --entitlement entitlements/lab.entitle ^
        --host node-1 --store records/entitle_records.log
    python run.py report --store records/entitle_records.log
"""

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

from entitle import checkpoints, encryption, entitlements, host, revocation_list, revoke, signing, tracking
from entitle.common import EntitleError
from entitle.records import ALL_RECORD_TYPES, RecordStore
from entitle.report import build_report, format_text
from version import __version__

PREVIOUS_ENCRYPTION_NOTE = (
    "NOTE: this file still uses the previous encryption (BSR2 Alpha 3). "
    "Run 'python run.py migrate' to re-seal it with the current encryption."
)
SHARED_KEY_NOTE = (
    "NOTE: this is a shared-key entitlement: anyone who can verify it can also issue one. "
    "Run 'python run.py migrate --signing-key ...' to convert it to a signed entitlement."
)
EXIT_REFUSED = 3
MASTER_KEY_ENV = "ENTITLE_MASTER_KEY"
PASSPHRASE_ENV = "ENTITLE_PASSPHRASE"


class _Parser(argparse.ArgumentParser):
    """No abbreviated options: --passphrase must never quietly mean --passphrase-file."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)


class _VersionAction(argparse.Action):
    """--version: the version, then the linked encryption and signatures (resolved only when asked)."""

    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        print(f"Entitle {__version__}")
        print(encryption.status().describe())
        print(encryption.signature_status().describe())
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


# Secrets: never required on the command line ------------------------------------------------------

def _read_secret_file(path):
    return Path(path).read_bytes().decode("utf-8-sig").rstrip("\r\n")


def _master_key(args, *, required=True):
    if getattr(args, "master_key", None):
        return args.master_key
    if getattr(args, "master_key_file", None):
        return _read_secret_file(args.master_key_file)
    if os.environ.get(MASTER_KEY_ENV):
        return os.environ[MASTER_KEY_ENV]
    if required:
        raise ValueError(f"a master key is required: use --master-key-file, or set {MASTER_KEY_ENV}.")
    return None


def _passphrase(args, *, confirm=False):
    if getattr(args, "passphrase_file", None):
        return _read_secret_file(args.passphrase_file)
    if os.environ.get(PASSPHRASE_ENV):
        return os.environ[PASSPHRASE_ENV]
    if sys.stdin is not None and sys.stdin.isatty():
        first = getpass.getpass("Signing key passphrase: ")
        if confirm and getpass.getpass("Repeat the passphrase: ") != first:
            raise ValueError("the two passphrases do not match.")
        return first
    raise ValueError(f"a passphrase is required: use --passphrase-file, or set {PASSPHRASE_ENV}.")


def _signing_key(args):
    return signing.load_signing_key(args.signing_key, _passphrase(args)) if args.signing_key else None


def _public_keys(args):
    return signing.load_public_keys(args.public_key) if getattr(args, "public_key", None) else None


def _entitlement_keys(args, path):
    """What verification of the file at path needs: (master_key, public_keys)."""
    public_keys = _public_keys(args)
    text = entitlements.read_entitlement_file(path)
    master_key = None if entitlements.is_signed(text) else _master_key(args)
    if entitlements.is_signed(text) and not public_keys:
        raise ValueError(f"{Path(path).name} is a signed entitlement; give the issuer's public key with --public-key.")
    return master_key, public_keys


def _strict(args, refused):
    return EXIT_REFUSED if refused and getattr(args, "strict", False) else 0


# Commands -----------------------------------------------------------------------------------------

def _cmd_keys_generate(args):
    public = signing.generate_key_pair(
        name=args.name,
        signing_key_path=args.signing_key,
        public_key_path=args.public_key,
        passphrase=_passphrase(args, confirm=True),
        overwrite=args.force,
        allow_in_repository=args.allow_in_repository,
    )
    print(f"Signing key (keep private, never share): {args.signing_key}")
    print(f"Public key (give to every lab and program that verifies): {args.public_key}")
    _print_json(public.to_dict())
    return 0


def _cmd_keys_show(args):
    _print_json(signing.load_public_key(args.key).to_dict())
    return 0


def _cmd_fingerprint(args):
    print(host.machine_fingerprint())
    return 0


def _cmd_issue(args):
    signing_key = _signing_key(args)
    payload = entitlements.issue_entitlement(
        issuer=args.issuer,
        subject=args.subject,
        product=args.product,
        entitlement_id=args.entitlement_id,
        master_key=None if signing_key else _master_key(args),
        signing_key=signing_key,
        drbg_seed=args.drbg_seed,
        drbg_personalization=args.drbg_personalization,
        output=args.output,
        expires=args.expires,
        not_before=args.not_before,
        machines=args.machine,
        enterprise=args.enterprise,
        modify=args.modify,
        fork=args.fork,
        export_source=args.export_source,
        redistribute=args.redistribute,
        deployment_limit=None if args.unlimited else args.deployment_limit,
        support_tier=args.support_tier,
        overwrite=args.force,
    )
    print("Signed entitlement created:" if signing_key else "Protected entitlement created:")
    print(args.output)
    print()
    print("Payload summary:")
    _print_json(payload)
    if not signing_key:
        print()
        print(SHARED_KEY_NOTE)
    return 0


def _cmd_verify(args):
    master_key, public_keys = _entitlement_keys(args, args.file)
    result = entitlements.verify_entitlement(
        issuer=args.issuer,
        subject=args.subject,
        product=args.product,
        master_key=master_key,
        public_keys=public_keys,
        revocation_list=args.revocation_list,
        store=RecordStore(args.store) if args.store else None,
        machine_id=args.machine,
        host_state=host.HostState(args.state) if args.state else None,
        path=args.file,
    )
    _print_json(result.to_dict())
    print()
    if result.allowed:
        print("VERIFIED: entitlement is valid.")
        if entitlements.uses_previous_encryption(args.file):
            print(PREVIOUS_ENCRYPTION_NOTE)
        elif master_key is not None:
            print(SHARED_KEY_NOTE)
        return 0
    print(f"DENIED: {result.reason}")
    return 1


def _cmd_inspect(args):
    _print_json(entitlements.inspect_entitlement(args.file))
    print()
    print("UNVERIFIED: this shows what the file claims. Only verify proves who issued it.")
    return 0


def _cmd_migrate(args):
    signing_key = _signing_key(args)
    outcome = entitlements.migrate_entitlement(
        issuer=args.issuer,
        subject=args.subject,
        product=args.product,
        master_key=_master_key(args),
        signing_key=signing_key,
        path=args.file,
    )
    if outcome["reason"] == "converted_to_signed":
        print(f"MIGRATED: {args.file} is now a signed entitlement (Ed25519).")
        print("Verify it with the public key (--public-key); Entitle versions before 0.7.0 cannot open it.")
    elif outcome["migrated"]:
        print(f"MIGRATED: {args.file} now uses the current encryption (BSR2-S64-SIV).")
        print("Entitle versions before 0.5.0 cannot open it; keep a copy if one of them must.")
    elif outcome["reason"] == "already_signed":
        print(f"UNCHANGED: {args.file} is already a signed entitlement.")
    else:
        print(f"UNCHANGED: {args.file} already uses the current encryption.")
    return 0


def _cmd_deploy(args):
    master_key, public_keys = _entitlement_keys(args, args.entitlement)
    outcome = tracking.deploy_from_file(
        issuer=args.issuer,
        subject=args.subject,
        product=args.product,
        master_key=master_key,
        public_keys=public_keys,
        revocation_list=args.revocation_list,
        entitlement_path=args.entitlement,
        host=args.host,
        store=RecordStore(args.store),
        environment=args.environment,
        notes=args.notes,
    )
    _print_json(outcome)
    return _strict(args, not outcome["recorded"])


def _cmd_release(args):
    outcome = tracking.release_deployment(
        RecordStore(args.store), product=args.product, subject=args.subject,
        entitlement_id=args.entitlement_id, host=args.host, reason=args.reason,
    )
    _print_json(outcome)
    return _strict(args, not outcome["released"])


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


def _cmd_publish(args):
    payload = revocation_list.publish_revocation_list(
        RecordStore(args.store), _signing_key(args), issuer=args.issuer, output=args.output,
    )
    _print_json(payload)
    print()
    print(f"Signed revocation list written to {args.output} (sequence {payload['sequence']}).")
    return 0


def _cmd_checkpoint_create(args):
    payload = checkpoints.create_checkpoint(
        RecordStore(args.store), _signing_key(args), output=args.output, overwrite=args.force
    )
    _print_json(payload)
    print()
    print(f"Signed checkpoint written to {args.output}. Keep it where the log's operator cannot change it.")
    return 0


def _cmd_checkpoint_verify(args):
    result = checkpoints.verify_checkpoint(RecordStore(args.store), args.checkpoint, _public_keys(args))
    _print_json(result)
    print()
    if result["valid"]:
        print(f"VERIFIED: the first {result['record_count']} records are exactly as checkpointed.")
        return 0
    print(f"FAILED: {result['reason']}")
    return 1


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
    return _strict(args, not report["chain"]["valid"])


def _open_window():
    try:
        from gui.window import launch
    except ModuleNotFoundError as exc:
        if exc.name not in ("tkinter", "_tkinter"):
            raise
        raise EntitleError("The window needs tkinter, which this Python installation does not provide.") from exc
    launch()
    return 0


def _cmd_gui(args):
    return _open_window()


def _open_window_or_show_usage(parser):
    """No command given: open the window, and if that cannot be done show the usage before the error."""
    try:
        return _open_window()
    except EntitleError:
        parser.print_help()
        raise


# Parser -------------------------------------------------------------------------------------------

def _add_store(parser, *, required=True, help_text="Record store file path."):
    parser.add_argument("--store", required=required, help=help_text)


def _add_identity(parser, *, required=True):
    parser.add_argument("--issuer", required=required, help="Issuer ID.")
    parser.add_argument("--subject", required=required, help="Customer, lab or organization ID.")
    parser.add_argument("--product", required=required, help="Product ID.")


def _add_master_key(parser):
    parser.add_argument(
        "--master-key", default=None,
        help=f"Shared master key text (visible in the process list; prefer --master-key-file or {MASTER_KEY_ENV}).",
    )
    parser.add_argument("--master-key-file", default=None, help="File holding the shared master key.")


def _add_signing_key(parser, *, required=False, help_text="Issuer signing key file (signed format)."):
    parser.add_argument("--signing-key", required=required, default=None, help=help_text)
    parser.add_argument(
        "--passphrase-file", default=None,
        help=f"File holding the signing key passphrase (or set {PASSPHRASE_ENV}, or type it when asked).",
    )


def _add_public_keys(parser, *, required=False):
    parser.add_argument(
        "--public-key", action="append", required=required, default=None,
        help="Issuer public key file; repeat to trust several keys.",
    )


def _add_drbg(parser):
    parser.add_argument("--drbg-seed", default=None, help="Shared-key only: extra DRBG seed text (64 bytes or more).")
    parser.add_argument(
        "--drbg-personalization", default=None, help="Shared-key only: DRBG personalization text (16 bytes or more)."
    )


def _add_strict(parser, what):
    parser.add_argument("--strict", action="store_true", help=f"Exit {EXIT_REFUSED} when {what}.")


def build_parser():
    parser = _Parser(
        prog="run.py",
        description="Entitle: offline software rights management with signed entitlements and a tamper-evident log.",
    )
    parser.add_argument("-V", "--version", action=_VersionAction, help="Show the version and the linked cryptography.")
    commands = parser.add_subparsers(dest="command", metavar="command")

    keys = commands.add_parser("keys", help="Create or show issuer signing keys.")
    key_commands = keys.add_subparsers(dest="keys_command", metavar="action", required=True)
    generate = key_commands.add_parser("generate", help="Create an issuer key pair.")
    generate.add_argument("--name", required=True, help="Key name, usually the issuer ID.")
    generate.add_argument("--signing-key", required=True, help="Where to write the private signing key.")
    generate.add_argument("--public-key", required=True, help="Where to write the public key.")
    generate.add_argument("--passphrase-file", default=None, help=f"Passphrase file (or {PASSPHRASE_ENV}, or a prompt).")
    generate.add_argument("--force", action="store_true", help="Overwrite existing key files.")
    generate.add_argument(
        "--allow-in-repository", action="store_true",
        help="Allow the signing key inside a Git working tree (refused by default, so it is never committed).",
    )
    generate.set_defaults(handler=_cmd_keys_generate)
    show = key_commands.add_parser("show", help="Show a key file's public details and key ID.")
    show.add_argument("--key", required=True, help="Public or signing key file.")
    show.set_defaults(handler=_cmd_keys_show)

    fingerprint = commands.add_parser("fingerprint", help="Print this machine's fingerprint, for --machine.")
    fingerprint.set_defaults(handler=_cmd_fingerprint)

    issue = commands.add_parser("issue", help="Create an entitlement (signed with --signing-key, or shared-key).")
    _add_identity(issue)
    issue.add_argument("--entitlement-id", required=True, help="Entitlement ID.")
    issue.add_argument(
        "--expires", default=None,
        help="Expiration ISO timestamp, for example 2027-01-31T23:59:59Z (a date alone means 00:00 UTC that day).",
    )
    issue.add_argument("--not-before", default=None, help="Signed only: ISO timestamp before which it is not valid.")
    issue.add_argument(
        "--machine", action="append", default=None,
        help="Signed only: bind to a machine fingerprint (from 'run.py fingerprint'); repeat for several.",
    )
    issue.add_argument("--output", required=True, help="Output .entitle path.")
    issue.add_argument("--force", action="store_true", help="Replace an existing file at --output.")
    _add_signing_key(issue, help_text="Issuer signing key file: issue a signed entitlement (recommended).")
    _add_master_key(issue)
    _add_drbg(issue)
    issue.add_argument("--enterprise", action="store_true", help="Grant enterprise feature rights.")
    issue.add_argument("--modify", action="store_true", help="Grant private modification rights.")
    issue.add_argument("--fork", action="store_true", help="Grant internal fork rights.")
    issue.add_argument("--export-source", action="store_true", help="Grant source export rights.")
    issue.add_argument("--redistribute", action="store_true", help="Grant redistribution rights.")
    limit = issue.add_mutually_exclusive_group()
    limit.add_argument("--deployment-limit", type=int, default=1, help="Maximum concurrent deployments.")
    limit.add_argument("--unlimited", action="store_true", help="No deployment limit.")
    issue.add_argument("--support-tier", default="standard", help="Support tier label.")
    issue.set_defaults(handler=_cmd_issue)

    verify = commands.add_parser("verify", help="Verify an entitlement.")
    _add_identity(verify)
    verify.add_argument("--file", required=True, help="Entitlement file.")
    _add_public_keys(verify)
    _add_master_key(verify)
    verify.add_argument("--revocation-list", default=None, help="Signed revocation list to check against.")
    _add_store(verify, required=False, help_text="Record store whose revocations to check against.")
    verify.add_argument("--machine", default=None, help="Check against this fingerprint instead of this machine's.")
    verify.add_argument("--state", default=None, help="Host state file: refuse a wound-back clock or an older list.")
    verify.set_defaults(handler=_cmd_verify)

    inspect = commands.add_parser("inspect", help="Show what an entitlement file claims, without verifying it.")
    inspect.add_argument("--file", required=True, help="Entitlement file.")
    inspect.set_defaults(handler=_cmd_inspect)

    migrate = commands.add_parser(
        "migrate", help="Re-seal a pre-0.5.0 file, or convert a shared-key file to signed with --signing-key."
    )
    _add_identity(migrate)
    _add_master_key(migrate)
    _add_signing_key(migrate, help_text="Convert to a signed entitlement with this signing key.")
    migrate.add_argument("--file", required=True, help="Entitlement file, replaced in place.")
    migrate.set_defaults(handler=_cmd_migrate)

    track = commands.add_parser("track", help="Record deployments, releases, forks and provenance.")
    track_commands = track.add_subparsers(dest="track_command", metavar="action", required=True)
    deploy = track_commands.add_parser("deploy", help="Record a governed deployment.")
    _add_identity(deploy)
    _add_public_keys(deploy)
    _add_master_key(deploy)
    deploy.add_argument("--entitlement", required=True, help="Entitlement file.")
    deploy.add_argument("--revocation-list", default=None, help="Signed revocation list to check against.")
    deploy.add_argument("--host", required=True, help="Deployment host or node ID.")
    deploy.add_argument("--environment", default=None)
    deploy.add_argument("--notes", default=None)
    _add_store(deploy)
    _add_strict(deploy, "the deployment is refused")
    deploy.set_defaults(handler=_cmd_deploy)

    release = track_commands.add_parser("release", help="Release a host's deployment, freeing its seat.")
    release.add_argument("--product", required=True)
    release.add_argument("--subject", required=True)
    release.add_argument("--entitlement-id", required=True)
    release.add_argument("--host", required=True)
    release.add_argument("--reason", default=None)
    _add_store(release)
    _add_strict(release, "nothing was released")
    release.set_defaults(handler=_cmd_release)

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

    revoke_group = commands.add_parser("revoke", help="Revoke, reinstate, check, or publish a revocation list.")
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
    publish = revoke_commands.add_parser("publish", help="Write a signed revocation list for labs and programs.")
    publish.add_argument("--issuer", required=True, help="Issuer ID the list is for.")
    _add_signing_key(publish, required=True, help_text="Issuer signing key file.")
    publish.add_argument("--output", required=True, help="Revocation list file to write.")
    _add_store(publish)
    publish.set_defaults(handler=_cmd_publish)

    checkpoint = commands.add_parser("checkpoint", help="Sign or check a checkpoint of the record log.")
    checkpoint_commands = checkpoint.add_subparsers(dest="checkpoint_command", metavar="action", required=True)
    create = checkpoint_commands.add_parser("create", help="Sign the log's current length and head hash.")
    _add_signing_key(create, required=True, help_text="Signing key file.")
    create.add_argument("--output", required=True, help="Checkpoint file to write.")
    create.add_argument("--force", action="store_true", help="Replace an existing checkpoint file.")
    _add_store(create)
    create.set_defaults(handler=_cmd_checkpoint_create)
    check_point = checkpoint_commands.add_parser("verify", help="Prove the log still holds a checkpointed prefix.")
    _add_public_keys(check_point, required=True)
    check_point.add_argument("--checkpoint", required=True, help="Checkpoint file.")
    _add_store(check_point)
    check_point.set_defaults(handler=_cmd_checkpoint_verify)

    report = commands.add_parser("report", help="Audit the record store and verify its hash chain.")
    _add_store(report)
    report.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    report.add_argument("--output", default=None, help="Write the report to this file instead of the screen.")
    _add_strict(report, "the hash chain is broken")
    report.set_defaults(handler=_cmd_report)

    gui = commands.add_parser("gui", help="Open the desktop window.")
    gui.set_defaults(handler=_cmd_gui)
    return parser


def main(argv=None):
    _make_output_safe()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command is None:
            return _open_window_or_show_usage(parser)
        return args.handler(args)
    except (EntitleError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
