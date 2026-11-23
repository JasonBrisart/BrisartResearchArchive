"""
File: cli.py

Purpose
-------
Command-line front end for the Brisart Research Archive: a numbered menu
and direct subcommands to run TFL, analyze one saved session or several,
list sessions, and show where they are saved. Standard library only;
never imports Tkinter, so it runs on Python builds without Tk.

Communication / relationships
-----------------------------
- run.py forwards "python run.py --cli ..." to main().
- Runs TFL through frameworks/TFL/cli_runner.run_cli(), writing to
  config/runtime.get_tfl_output_dir(): the same Output Directory setting
  the GUI uses.
- Analyzes through frameworks/TFL/analysis: analyze_output() for the
  newest session, analyze_outputs() for named files or every session.
- Picks the newest session and lists sessions with
  frameworks/TFL/output.latest_session_file() and list_session_files() in
  the folder from get_tfl_output_dir().
- Prints DISPLAY_VERSION from version.py in the menu banner.

Settings / parameters
---------------------
- python cli.py                       menu: 1 Run TFL, 2 Analyze Latest
                                      Session, 3 List Sessions, 4 Show
                                      Output Folder, Q Quit
- python cli.py run                   run TFL
- python cli.py analyze               analyze the newest session
- python cli.py analyze --file P ...  analyze P; repeat --file to pool
                                      several sessions
- python cli.py analyze --all         pool every saved session
- python cli.py sessions              list sessions, oldest first
- python cli.py where                 print the TFL output folder
- Exit status: 0 on success; 1 when analyze --file names a file that does
  not exist; 2 when --file and --all are combined (rejected by argparse).

Edge cases
----------
- Ctrl+C or end-of-input at the menu exits quietly with status 0; an
  invalid menu choice prints a message and shows the menu again.
- analyze and analyze --all with no saved sessions print a message and
  exit 0.
- If any --file does not exist, every missing file is named, nothing is
  analyzed, and the status is 1.
- One --file gives the same report as analyze --file would for a single
  session; two or more are pooled, and the same path twice counts once.
- run always exits 0, including when the run was stopped with Ctrl+C or
  left at the startup menu; answers already given are in the session CSV.
- The menu ignores the status of the action it ran and shows itself again.

Known limitations
-----------------
- The menu's Analyze Latest Session analyzes the newest session only;
  pooling needs the --file or --all flags.
- The console cannot interrupt a blocking prompt, so a timed answer typed
  late is recorded as a timeout instead of a live countdown expiring.
- sessions lists each file's last-saved date and name, not its trial
  count or label; the analysis report shows those.
- There is no command to delete, export, or rename sessions.

Examples
--------
- python cli.py run
- python cli.py analyze --file a.csv --file b.csv
- python cli.py analyze --all
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
from frameworks.TFL.analysis import analyze_output, analyze_outputs  # noqa: E402
from frameworks.TFL.cli_runner import run_cli  # noqa: E402
from frameworks.TFL.output import latest_session_file, list_session_files  # noqa: E402
from version import DISPLAY_VERSION  # noqa: E402


def print_header() -> None:
    print("\n" + "=" * 80)
    print("BRISART RESEARCH ARCHIVE")
    print(f"COMMAND-LINE EXECUTION SUITE  ({DISPLAY_VERSION})")
    print("=" * 80)


def command_run() -> int:
    run_cli(output_dir=get_tfl_output_dir())
    return 0


def command_analyze(files: list[str] | None = None, all_sessions: bool = False) -> int:
    if all_sessions:
        paths = list_session_files(get_tfl_output_dir())
        if not paths:
            print(f"No TFL sessions yet in {get_tfl_output_dir()}")
            return 0
        print(analyze_outputs(paths))
        return 0
    if files:
        missing = [name for name in files if not Path(name).exists()]
        for name in missing:
            print(f"File not found: {name}")
        if missing:
            return 1
        print(analyze_outputs([Path(name) for name in files]))
        return 0
    latest = latest_session_file(get_tfl_output_dir())
    if latest is None:
        print(f"No TFL sessions yet in {get_tfl_output_dir()}")
        return 0
    print(analyze_output(latest))
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
    analyze = sub.add_parser("analyze", help="analyze the newest TFL session, chosen --file(s), or --all")
    chosen = analyze.add_mutually_exclusive_group()
    chosen.add_argument("--file", action="append", default=None, metavar="PATH",
                        help="a session CSV; repeat to pool several")
    chosen.add_argument("--all", action="store_true", help="pool every saved session")
    sub.add_parser("sessions", help="list saved TFL sessions")
    sub.add_parser("where", help="print the TFL output folder")
    args = parser.parse_args(argv)
    if args.command is None:
        return interactive()
    if args.command == "analyze":
        return command_analyze(args.file, args.all)
    return {"run": command_run, "sessions": command_sessions, "where": command_where}[args.command]()


if __name__ == "__main__":
    sys.exit(main())

