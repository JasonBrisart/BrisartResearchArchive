r"""
File: cli.py

Purpose
-------
Provide offline CLI commands for local files, notes and questions.

Communication / relationships
-----------------------------
Initializes native_path and state before creating BrisartService.

Settings / parameters
---------------------
Commands: counts, ask, import, note, notes; no web flags.

Edge cases
----------
Unknown research or --web options are rejected by argparse.

Known limitations
-----------------
No desktop is needed, but the external Native APIs are required.

Examples
--------
python cli.py ask "question"
"""
from __future__ import annotations
import argparse

from brisart_ai import native_path

native_path.install()

from brisart_ai import state  # noqa: E402
from brisart_ai.core.service import BrisartService  # noqa: E402
from brisart_ai.knowledge.index import DEFAULT_DB  # noqa: E402

def main(argv=None):
    parser = argparse.ArgumentParser(description="BrisartAI research CLI")
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite index path")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("counts")
    ask = sub.add_parser("ask"); ask.add_argument("question")
    imp = sub.add_parser("import"); imp.add_argument("paths", nargs="+")
    note = sub.add_parser("note"); note.add_argument("title"); note.add_argument("body")
    notes = sub.add_parser("notes"); notes.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)
    state.migrate_legacy_state()
    service = BrisartService(args.db)
    try:
        if args.command == "counts":
            total, files, web = service.counts()
            print(f"Sources: {total} (files: {files}, web: {web})")
        elif args.command == "ask": print(service.ask(args.question))
        elif args.command == "import": print(service.import_paths(args.paths))
        elif args.command == "note": print(service.add_note(args.title, args.body))
        elif args.command == "notes": print(service.list_notes(args.limit))
    finally:
        service.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
