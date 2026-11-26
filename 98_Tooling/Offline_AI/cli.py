r"""
File: cli.py

Purpose
-------
Expose local imports, notes, counts and cited questions without Tk.

Public operations: main (argv=None).

Communication / relationships
-----------------------------
Installs Native APIs before constructing BrisartService; runs legacy state migration
before opening the index.

Direct project imports: brisart_ai, brisart_ai.core.service, brisart_ai.knowledge.index.

Concrete calls within this file include native_path.install, state.migrate_legacy_state,
service.close, service.counts, service.ask, service.import_paths, service.add_note,
service.list_notes.

Settings / parameters
---------------------
Use --db before a subcommand to override the SQLite path; BRISARTAI_STATE_DIR controls
default state.

Call signatures: main(argv=None).

Edge cases
----------
The service closes in finally after command execution; unrecognized commands fail
through argparse.

Explicit exception branches or raised errors in this file include SystemExit.

Known limitations
-----------------
No web search or desktop controls. The external APIs must resolve even for help.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Any broader behavior
depends on the documented upstream inputs and downstream consumers. No compatibility adapter
or speculative extension point has been added as part of this pass.

Examples
--------
python cli.py ask "What is the permit fee?"

For a concrete entry point, inspect `main`; invoke it through the existing application entry
point or its documented caller. The example above is illustrative of this file's present
interface; do not treat it as an instruction to create additional state or call private
functions directly.
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
