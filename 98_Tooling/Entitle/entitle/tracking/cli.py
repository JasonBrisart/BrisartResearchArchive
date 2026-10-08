"""
Entitle Tracking — CLI

The ``track`` subcommand group: deploy, fork, provenance, and list.

This is a thin argument-parsing wrapper. Every command calls directly into the
same functions the GUI uses (``deploy_from_file``, ``record_fork``,
``record_provenance``, ``list_records``), so the CLI and GUI can never drift out
of sync. ``main.py`` dispatches ``track`` here via its ``COMMAND_MODULES`` table.
"""
import argparse
import json

from .deploy import deploy_from_file
from .fork import record_fork
from .provenance import record_provenance
from .query import list_records


def _cmd_deploy(args):
    outcome = deploy_from_file(
        issuer=args.issuer,
        subject=args.subject,
        product=args.product,
        master_key=args.master_key,
        entitlement_path=args.entitlement,
        host=args.host,
        store=args.store,
        environment=args.environment,
        notes=args.notes,
    )
    print(json.dumps(outcome, indent=2, ensure_ascii=False))


def _cmd_fork(args):
    record = record_fork(
        store=args.store,
        product=args.product,
        source_version=args.source_version,
        fork_name=args.fork_name,
        maintainer=args.maintainer,
        environment=args.environment,
        notes=args.notes,
    )
    print(json.dumps(record, indent=2, ensure_ascii=False))


def _cmd_provenance(args):
    record = record_provenance(
        store=args.store,
        product=args.product,
        origin=args.origin,
        version=args.version,
        custodian=args.custodian,
        previous_version=args.previous_version,
        notes=args.notes,
    )
    print(json.dumps(record, indent=2, ensure_ascii=False))


def _cmd_list(args):
    records = list_records(store=args.store, record_type=args.type)
    print(json.dumps(records, indent=2, ensure_ascii=False))


def build_parser():
    parser = argparse.ArgumentParser(
        prog="track",
        description="Record deployments, forks, and provenance for Entitle.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    deploy = subparsers.add_parser("deploy", help="Record a governed deployment.")
    deploy.add_argument("--issuer", required=True)
    deploy.add_argument("--subject", required=True)
    deploy.add_argument("--product", required=True)
    deploy.add_argument("--master-key", required=True)
    deploy.add_argument("--entitlement", required=True, help="Protected .entitle file.")
    deploy.add_argument("--host", required=True, help="Deployment host or node ID.")
    deploy.add_argument("--environment", default=None)
    deploy.add_argument("--notes", default=None)
    deploy.add_argument("--store", required=True, help="Record store file path.")
    deploy.set_defaults(func=_cmd_deploy)

    fork = subparsers.add_parser("fork", help="Record an internal fork.")
    fork.add_argument("--product", required=True)
    fork.add_argument("--source-version", required=True)
    fork.add_argument("--fork-name", required=True)
    fork.add_argument("--maintainer", required=True)
    fork.add_argument("--environment", default=None)
    fork.add_argument("--notes", default=None)
    fork.add_argument("--store", required=True, help="Record store file path.")
    fork.set_defaults(func=_cmd_fork)

    provenance = subparsers.add_parser("provenance", help="Record provenance/ownership.")
    provenance.add_argument("--product", required=True)
    provenance.add_argument("--origin", required=True)
    provenance.add_argument("--version", required=True)
    provenance.add_argument("--previous-version", default=None)
    provenance.add_argument("--custodian", required=True)
    provenance.add_argument("--notes", default=None)
    provenance.add_argument("--store", required=True, help="Record store file path.")
    provenance.set_defaults(func=_cmd_provenance)

    listing = subparsers.add_parser("list", help="List records of a type.")
    listing.add_argument(
        "--type",
        default=None,
        help="deployment, fork, or provenance. Omit for all records.",
    )
    listing.add_argument("--store", required=True, help="Record store file path.")
    listing.set_defaults(func=_cmd_list)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0
