"""
Entitle Report

Audit and reporting for the Entitle record store.

Generates a governance report over deployments, forks, and provenance records,
and verifies the tamper-evident hash chain so you can confirm the log has not
been edited, truncated, or reordered.

Example:
    python main.py report --store records/entitle_records.log
"""
import argparse
import json
from pathlib import Path

from .record_types import RECORD_TYPE_DEPLOYMENT
from .records import RecordStore


def build_report(store):
    records = store.read_all()
    chain = store.verify_chain()
    counts = {}
    for record in records:
        record_type = record.get("record_type", "unknown")
        counts[record_type] = counts.get(record_type, 0) + 1
    deployments_by_product = {}
    for record in store.filter(record_type=RECORD_TYPE_DEPLOYMENT):
        product_id = record.get("data", {}).get("product_id", "unknown")
        deployments_by_product[product_id] = (
            deployments_by_product.get(product_id, 0) + 1
        )
    first_created = records[0]["created_at"] if records else None
    last_created = records[-1]["created_at"] if records else None
    return {
        "store": str(store.path),
        "record_count": len(records),
        "counts_by_type": counts,
        "deployments_by_product": deployments_by_product,
        "first_record_at": first_created,
        "last_record_at": last_created,
        "chain": chain.to_dict(),
    }


def build_report_for_path(store_path):
    """Convenience wrapper used by both the CLI and the GUI."""
    return build_report(RecordStore(store_path))


def format_text(report):
    lines = []
    lines.append("Entitle Audit Report")
    lines.append("=" * 20)
    lines.append(f"Store: {report['store']}")
    lines.append(f"Total records: {report['record_count']}")
    lines.append(f"First record: {report['first_record_at']}")
    lines.append(f"Last record:  {report['last_record_at']}")
    lines.append("")
    lines.append("Records by type")
    lines.append("-" * 20)
    if report["counts_by_type"]:
        for record_type, count in sorted(report["counts_by_type"].items()):
            lines.append(f"{record_type}: {count}")
    else:
        lines.append("(none)")
    lines.append("")
    lines.append("Deployments by product")
    lines.append("-" * 20)
    if report["deployments_by_product"]:
        for product_id, count in sorted(report["deployments_by_product"].items()):
            lines.append(f"{product_id}: {count}")
    else:
        lines.append("(none)")
    lines.append("")
    chain = report["chain"]
    lines.append("Chain integrity")
    lines.append("-" * 20)
    if chain["valid"]:
        lines.append(f"VERIFIED: hash chain intact across {chain['record_count']} records.")
    else:
        lines.append(
            f"BROKEN: {chain['reason']} at record index {chain['broken_index']}."
        )
    return "\n".join(lines)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="report",
        description="Audit and report on the Entitle record store.",
    )
    parser.add_argument("--store", required=True, help="Record store file path.")
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional file to write the report to. Prints to screen if omitted.",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    report = build_report_for_path(args.store)
    if args.format == "json":
        rendered = json.dumps(report, indent=2, ensure_ascii=False)
    else:
        rendered = format_text(report)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            handle.write(rendered)
            handle.write("\n")
        print(f"Report written to {path}")
    else:
        print(rendered)
    return 0
