"""
File: entitle/report.py

Purpose
-------
Summarize a record log for audit: how many records of each type, deployments per product, the
  time span covered, and whether the hash chain is intact. build_report returns plain data and
  format_text renders it as text; printing or saving it is the caller's job.

Communication / relationships
-----------------------------
Imports entitle/records.py (RECORD_TYPE_DEPLOYMENT); the RecordStore is passed in. Imported by
  cli.py (report, as text or JSON) and gui/tabs.py (Audit Report tab). Needs no encryption, so
  it works without 97_Encryption. Covered by tests/test_report.py.

Settings / parameters
---------------------
build_report(store) returns store (the path as text), store_exists, record_count (readable
  records), unreadable_records (lines that are not a record), counts_by_type,
  deployments_by_product, first_record_at, last_record_at and chain (valid, broken_index,
  reason, record_count). format_text(report) renders it under the heading "Entitle Audit Report",
  with "(none)" for empty sections and an "Unreadable records" line only when there are some.

Edge cases
----------
A store file that does not exist is reported with store_exists false and the text says so,
  rather than presenting a missing log as a verified one. A log with damaged lines still gets a
  full report: readable records are counted, unreadable ones are reported as a number, and the
  chain is BROKEN at the first damaged index (reason unparseable_record). An existing but empty
  log reports its chain as VERIFIED across 0 records. Records missing created_at report None for
  the time span instead of failing.

Known limitations
-----------------
A verified chain shows the records agree with each other, not that the log is complete: a log
  cut short at the end still verifies, and so does one rewritten from an edit onward. Keep an
  independent copy of the last entry hash if completeness matters. Counts are read from the
  whole file each time.

Examples
--------
From the directory containing main.py:

    from tempfile import TemporaryDirectory
    from entitle.records import RECORD_TYPE_FORK, RecordStore
    from entitle.report import build_report, format_text

    with TemporaryDirectory() as folder:
        store = RecordStore(f"{folder}/entitle_records.log")
        store.append(RECORD_TYPE_FORK, {"fork_name": "lab-a"})
        report = build_report(store)
        assert report["counts_by_type"] == {"fork": 1} and report["chain"]["valid"]
        print(format_text(report))
"""

from .records import RECORD_TYPE_DEPLOYMENT


def build_report(store):
    records = store.read_all(strict=False)
    chain = store.verify_chain()
    counts = {}
    for record in records:
        record_type = record.get("record_type", "unknown")
        counts[record_type] = counts.get(record_type, 0) + 1
    deployments_by_product = {}
    for record in records:
        if record.get("record_type") == RECORD_TYPE_DEPLOYMENT:
            product_id = record["data"].get("product_id", "unknown")
            deployments_by_product[product_id] = deployments_by_product.get(product_id, 0) + 1
    return {
        "store": str(store.path),
        "store_exists": store.path.exists(),
        "record_count": len(records),
        "unreadable_records": chain.record_count - len(records),
        "counts_by_type": counts,
        "deployments_by_product": deployments_by_product,
        "first_record_at": records[0].get("created_at") if records else None,
        "last_record_at": records[-1].get("created_at") if records else None,
        "chain": chain.to_dict(),
    }


def _section(lines, title, counts):
    lines.append(title)
    lines.append("-" * 20)
    if counts:
        for name, count in sorted(counts.items()):
            lines.append(f"{name}: {count}")
    else:
        lines.append("(none)")
    lines.append("")


def format_text(report):
    lines = ["Entitle Audit Report", "=" * 20, f"Store: {report['store']}"]
    if not report.get("store_exists", True):
        lines.append("Note: this store file does not exist, so there are no records to audit.")
    lines.append(f"Total records: {report['record_count']}")
    if report.get("unreadable_records"):
        lines.append(f"Unreadable records: {report['unreadable_records']} (not counted below)")
    lines.append(f"First record: {report['first_record_at']}")
    lines.append(f"Last record:  {report['last_record_at']}")
    lines.append("")
    _section(lines, "Records by type", report["counts_by_type"])
    _section(lines, "Deployments by product", report["deployments_by_product"])
    chain = report["chain"]
    lines.append("Chain integrity")
    lines.append("-" * 20)
    if chain["valid"]:
        lines.append(f"VERIFIED: hash chain intact across {chain['record_count']} records.")
    else:
        lines.append(f"BROKEN: {chain['reason']} at record index {chain['broken_index']}.")
    return "\n".join(lines)
