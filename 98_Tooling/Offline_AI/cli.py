r"""
File: cli.py

Purpose
-------
Expose index, question, note and research operations without starting the
desktop.

Communication / relationships
-----------------------------
Calls brisart_ai.native_path.install() before any other brisart_ai import and
brisart_ai.state.migrate_legacy_state() before opening the index. Uses the
same brisart_ai.core.service.BrisartService as the GUI.

Settings / parameters
---------------------
--db selects the SQLite database (default: the index in the per-user state
folder, see brisart_ai/state.py); research accepts --limit and --depth.

Edge cases
----------
Always closes database resources, including after an operation fails.
A failed move of old saved state prints a warning to stderr and the command
still runs.

Known limitations
-----------------
- Web research requires network access.
- The Brisart native stack must be reachable: native_path.install() looks in
  BRISART_NATIVE_API or the external 94_Native_API's folder above this project.
- Saved state moves to the per-user folder the first time any entry point
  runs after an upgrade; see brisart_ai/state.py.

Examples
--------
python cli.py counts
python cli.py ask "What do my documents say?"
python cli.py research "local history" --limit 3
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
    ask.add_argument("--web", action="store_true", help="Enable web research for this query")
    research = sub.add_parser("research"); research.add_argument("query")
    research.add_argument("--limit", type=int, default=5); research.add_argument("--depth", type=int, default=0)
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
        elif args.command == "ask": print(service.ask(args.question, force_web=args.web))
        elif args.command == "research": print(service.research(args.query, limit=args.limit, depth=args.depth))
        elif args.command == "import": print(service.import_paths(args.paths))
        elif args.command == "note": print(service.add_note(args.title, args.body))
        elif args.command == "notes": print(service.list_notes(args.limit))
    finally:
        service.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
