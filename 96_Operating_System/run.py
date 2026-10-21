r"""
File: run.py

Purpose
-------
Route BrisartOS runtime and maintenance commands to child interpreters launched
from the project root, and return the exit status of the chosen child.

Public interface:
- main(argv=None) -- Parse the command line, launch the chosen command in a
  child interpreter and return its exit status.

Design notes:

The root is derived from this file rather than the caller working directory.
Every command, including test, runs as a child process using the same
executable with -B and -S; this file holds only the routing table. Test
discovery, concurrency and result aggregation live in tools/runtests.py. Only
start and test forward their remaining options. Router execution is exercised
by subprocess tests in brisartos/shell/tests/test_console.py and
tools/tests/test_tools.py; those launch references are not static imports.

Communication / relationships
-----------------------------
Standard library: argparse, pathlib, subprocess, sys.
Imported by: no other module in this tree imports it directly.
Covered by tests: none directly.

Settings / parameters
---------------------
- ROOT = Path(__file__).resolve().parent -- The directory containing this file,
  resolved to an absolute path.
- COMMANDS -- Maps each routed command to the interpreter arguments it
  launches.
- FORWARDS_OPTIONS = ('start', 'test') -- The commands whose remaining
  command-line options are passed on to the child program.
- INTERPRETER = [sys.executable, '-B', '-S'] -- The interpreter and flags used
  for every child process.

Edge cases
----------
An unknown command exits with status 2 (argparse). A child process exit status
becomes the exit status of this program. For test that status is 0 when every
folder passes, 1 when any fails and 2 when a filter matches no folder.

Known limitations
-----------------
- Only start and test forward extra options. The other commands ignore trailing
  arguments.
- It launches programs. It does not build images, create boot media or check
  that a build is installable.

Examples
--------
Run from the repository root.

::

    python -B run.py start
    python -B run.py start --memory
    python -B run.py test
    python -B run.py test kernel shell
    python -B run.py audit
    python -B run.py headers
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMMANDS = {
    'start': ['-m', 'brisartos.shell.console'],
    'rom': ['-m', 'brisartos.machine.machine'],
    'audit': ['tools/audit.py'],
    'headers': ['tools/headers.py'],
    'test': ['tools/runtests.py'],
}
FORWARDS_OPTIONS = ('start', 'test')
INTERPRETER = [sys.executable, '-B', '-S']


def main(argv=None):
    parser = argparse.ArgumentParser(description='BrisartOS command router. Python standard library only.')
    parser.add_argument('command', choices=sorted(COMMANDS))
    parser.add_argument('options', nargs=argparse.REMAINDER)
    arguments = parser.parse_args(argv)
    extra = arguments.options if arguments.command in FORWARDS_OPTIONS else []
    return subprocess.call(INTERPRETER + COMMANDS[arguments.command] + extra, cwd=ROOT)


if __name__ == '__main__':
    raise SystemExit(main())
