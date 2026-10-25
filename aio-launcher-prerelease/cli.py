"""
File: cli.py

Purpose
-------
Command-line front end for the Brisart Research Archive, in the spirit
of the 02_Execution launcher: a numbered menu plus direct subcommands.
Standard library only; never imports Tkinter.

Communication / relationships
-----------------------------
- Runs TFL through frameworks/TFL/cli_runner.run_cli().
- Analyzes through frameworks/TFL/analysis.analyze_output().
- Lists sessions through frameworks/TFL/output.list_session_files().
- Resolves the output folder through config/runtime.get_tfl_output_dir(),
  the same saved setting the GUI uses.
- run.py forwards "python run.py --cli ..." here.

Settings / parameters
---------------------
- python cli.py                      interactive menu
- python cli.py run                  run TFL
- python cli.py analyze [--file P]   analyze the latest session, or P
- python cli.py sessions             list saved sessions, newest last
- python cli.py where                print the TFL output folder

Edge cases
----------
- Ctrl+C or end-of-input at the main menu exits cleanly.
- analyze with no sessions prints a message instead of failing.
- Exit code 0 on success, 1 when analyze is given a missing file.

Known limitations
-----------------
- The self-updater is GUI-only; the CLI never checks for updates.

Examples
--------
- python cli.py run
- python run.py --cli analyze --file tfl_output_2026-10-24_18-45-12.csv
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.runtime import get_tfl_output_dir  # noqa: E402
from frameworks.TFL.analysis import analyze_output  # noqa: E402
from frameworks.TFL.cli_runner import run_cli  # noqa: E402
from frameworks.TFL.output import list_session_files  # noqa: E402
from version import DISPLAY_VERSION  # noqa: E402


def print_header() -> None:
    print("\n" + "=" * 80)
    print("BRISART RESEARCH ARCHIVE")
    print(f"COMMAND-LINE EXECUTION SUITE  ({DISPLAY_VERSION})")
    print("=" * 80)


def command_run() -> int:
    run_cli(output_dir=get_tfl_output_dir())
    return 0


def command_analyze(file: str | None = None) -> int:
    if file and not Path(file).exists():
        print(f"File not found: {file}")
        return 1
    print(analyze_output(Path(file) if file else None))
    return 0


def command_sessions() -> int:
    files = list_session_files(get_tfl_output_dir())
    if not files:
        print(f"No TFL sessions yet in {get_tfl_output_dir()}")
    for path in files:
        saved = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"{saved}  {path.name}")
    return 0


def command_where() -> int:
    print(get_tfl_output_dir())
    return 0


def interactive() -> int:
    actions = {"1": command_run, "2": command_analyze, "3": command_sessions, "4": command_where}
    while True:
        print_header()
        print("1. Run TFL")
        print("2. Analyze Latest Session")
        print("3. List Sessions")
        print("4. Show Output Folder")
        print("Q. Quit")
        try:
            choice = input("\nSelection: ").strip().upper()
            if choice == "Q":
                return 0
            if choice in actions:
                actions[choice]()
            else:
                print("Invalid choice. Please select 1-4 or Q.")
        except (KeyboardInterrupt, EOFError):
            print()
            return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cli.py", description="Brisart Research Archive command line")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", help="run TFL")
    analyze = sub.add_parser("analyze", help="analyze the latest TFL session, or --file")
    analyze.add_argument("--file", default=None)
    sub.add_parser("sessions", help="list saved TFL sessions")
    sub.add_parser("where", help="print the TFL output folder")
    args = parser.parse_args(argv)
    if args.command is None:
        return interactive()
    if args.command == "analyze":
        return command_analyze(args.file)
    return {"run": command_run, "sessions": command_sessions, "where": command_where}[args.command]()


if __name__ == "__main__":
    sys.exit(main())
