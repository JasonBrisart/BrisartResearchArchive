"""
File: cli.py

Purpose
-------
Command-line front end for the Brisart Research Archive, in the spirit of
the 02_Execution launcher: a numbered console menu plus direct
subcommands. Standard library only; never imports Tkinter.

Communication / relationships
-----------------------------
- Discovers frameworks through config/registries.py.
- Runs a framework through its FRAMEWORK_METADATA cli_module and
  cli_function; analyzes through analysis_module.analyze_output().
- Resolves output folders through config/runtime.py, the same settings
  file the GUI uses.
- main.py forwards "python main.py --cli ..." here.

Settings / parameters
---------------------
- python cli.py                         interactive menu
- python cli.py list                    list frameworks
- python cli.py run TFL                 run a framework
- python cli.py analyze TFL [--file P]  print an analysis report
- python cli.py where                   print the output folder

Edge cases
----------
- Reserved frameworks and frameworks without a CLI runner are listed but
  refused with a message, never a traceback.
- Exit code 0 on success, 1 for an unknown framework or missing runner.

Known limitations
-----------------
- The Archive self-updater is GUI-only; the CLI does not check for
  updates.

Examples
--------
- python cli.py run TFL
- python main.py --cli analyze TFL
"""
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.registries import get_framework, initialize_framework_registry  # noqa: E402
from config.runtime import get_framework_output_dir, get_output_folder  # noqa: E402


def read_version() -> str:
    try:
        return (ROOT / "version.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return "Unknown Version"


def print_header() -> None:
    print("\n" + "=" * 80)
    print("BRISART RESEARCH ARCHIVE")
    print(f"COMMAND-LINE EXECUTION SUITE  ({read_version()})")
    print("=" * 80)


def list_frameworks() -> list[dict]:
    registry = initialize_framework_registry()
    for item in registry:
        cli = "CLI" if item.get("cli_module") else "GUI only"
        print(f"  {item['id']:<6} {item['name']:<40} {item['status']:<12} {cli}")
    return registry


def _resolve(framework_id: str) -> dict | None:
    initialize_framework_registry()
    framework = get_framework(framework_id)
    if framework is None:
        print(f"No framework is registered with ID: {framework_id}")
    elif str(framework.get("status", "")).casefold() != "available":
        print(f"{framework['id']} is reserved and cannot run yet.")
        return None
    return framework


def run_framework(framework_id: str) -> int:
    framework = _resolve(framework_id)
    if framework is None:
        return 1
    module_name, function_name = framework.get("cli_module"), framework.get("cli_function")
    if not module_name or not function_name:
        print(f"{framework['id']} has no command-line runner.")
        return 1
    runner = getattr(importlib.import_module(module_name), function_name)
    runner(output_dir=get_framework_output_dir(framework["id"]))
    return 0


def analyze_framework(framework_id: str, file: str | None = None) -> int:
    framework = _resolve(framework_id)
    if framework is None:
        return 1
    module_name = framework.get("analysis_module")
    if not module_name:
        print(f"{framework['id']} has no analysis module.")
        return 1
    print(importlib.import_module(module_name).analyze_output(Path(file) if file else None))
    return 0


def choose_framework() -> str | None:
    available = [f for f in initialize_framework_registry()
                 if str(f.get("status", "")).casefold() == "available"]
    if not available:
        print("No frameworks are available.")
        return None
    for number, item in enumerate(available, start=1):
        print(f"{number}. {item['id']} - {item['name']}")
    choice = input("\nFramework number: ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(available):
        return available[int(choice) - 1]["id"]
    print("Invalid selection.")
    return None


def interactive() -> int:
    while True:
        print_header()
        print("1. Run Framework")
        print("2. Analyze Results")
        print("3. List Frameworks")
        print("4. Show Output Folder")
        print("Q. Quit")
        try:
            choice = input("\nSelection: ").strip().upper()
        except (KeyboardInterrupt, EOFError):
            print()
            return 0
        if choice == "Q":
            return 0
        try:
            if choice == "1":
                framework_id = choose_framework()
                if framework_id:
                    run_framework(framework_id)
            elif choice == "2":
                framework_id = choose_framework()
                if framework_id:
                    analyze_framework(framework_id)
            elif choice == "3":
                list_frameworks()
            elif choice == "4":
                print(get_output_folder())
            else:
                print("Invalid choice. Please select 1-4 or Q.")
        except (KeyboardInterrupt, EOFError):
            print("\nReturned to the main menu.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cli.py", description="Brisart Research Archive command line")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="list registered frameworks")
    run = sub.add_parser("run", help="run a framework")
    run.add_argument("framework")
    analyze = sub.add_parser("analyze", help="analyze framework output")
    analyze.add_argument("framework")
    analyze.add_argument("--file", default=None)
    sub.add_parser("where", help="print the output folder")
    args = parser.parse_args(argv)
    if args.command is None:
        return interactive()
    if args.command == "list":
        list_frameworks()
        return 0
    if args.command == "run":
        return run_framework(args.framework)
    if args.command == "analyze":
        return analyze_framework(args.framework, args.file)
    print(get_output_folder())
    return 0


if __name__ == "__main__":
    sys.exit(main())
