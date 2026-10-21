r"""
File: run.py

Purpose
-------
Route BrisartOS maintenance and runtime commands to child interpreters, or
coordinate filtered test-folder runs and aggregate their exit results.

Public interface:
- main(argv=None) -- Parse the command line, dispatch to the chosen command and
  return its exit status.

Design notes:

The root is derived from this file rather than the caller working directory.
Routed programs use the same executable with -B and -S; only start forwards
remaining options. Test discovery selects folders by path substrings and runs
up to eight concurrently, collecting each child output and reported test count
before printing the summary.

Router execution is exercised by subprocess tests in
brisartos/shell/tests/test_console.py; those launch references are not static
imports.

Communication / relationships
-----------------------------
Standard library: argparse, concurrent, pathlib, subprocess, sys, time.
Imported by: no other module in this tree imports it directly.
Covered by tests: none directly.

Settings / parameters
---------------------
- ROOT = Path(__file__).resolve().parent -- The directory containing this file,
  resolved to an absolute path.
- COMMANDS -- Maps each routed command to the interpreter arguments it
  launches; test is handled in-process.
- INTERPRETER = [sys.executable, '-B', '-S'] -- The interpreter and flags used
  for every child process.

Edge cases
----------
An unknown command exits with status 2 (argparse). A test filter that matches
no folder prints a message and returns 2. A child process's exit status becomes
the exit status of this program; the test command returns 1 if any folder
fails.

Known limitations
-----------------
- Only start forwards extra options (for example --memory). The other commands
  ignore trailing arguments.
- It launches programs. It does not build images, create boot media or check
  that a build is installable.
- Test folders run in separate processes, so a failing import in one folder
  cannot be seen by another, and the printed total counts only folders that
  ran.

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
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMMANDS = {
    'start': ['-m', 'brisartos.shell.console'],
    'rom': ['-m', 'brisartos.machine.machine'],
    'audit': ['tools/audit.py'],
    'headers': ['tools/headers.py'],
}
INTERPRETER = [sys.executable, '-B', '-S']


def _test_folders():
    found = [ROOT / 'tests'] + sorted(ROOT.glob('brisartos/*/tests')) + sorted(ROOT.glob('tools/tests'))
    return [folder for folder in found if folder.is_dir()]


def _run_test_folder(folder):
    started = time.time()
    result = subprocess.run(INTERPRETER + ['-m', 'unittest', 'discover', '-s', str(folder)],
                            cwd=ROOT, capture_output=True, text=True)
    output = result.stderr + result.stdout
    count = 0
    for line in output.splitlines():
        if line.startswith('Ran '):
            count = int(line.split()[1])
    return folder, result.returncode, count, time.time() - started, output


def _run_tests(filters):
    folders = [folder for folder in _test_folders()
               if not filters or any(item in folder.relative_to(ROOT).as_posix() for item in filters)]
    if not folders:
        print('no test folders match ' + ' '.join(filters))
        return 2
    started = time.time()
    with ThreadPoolExecutor(max_workers=min(8, len(folders))) as pool:
        results = list(pool.map(_run_test_folder, folders))
    failed, total = 0, 0
    for folder, code, count, seconds, output in results:
        total += count
        label = folder.relative_to(ROOT).as_posix()
        print(('ok    ' if code == 0 else 'FAIL  ') + label.ljust(34) + str(count).rjust(4) + ' tests  '
              + format(seconds, '5.1f') + 's')
        if code != 0:
            failed += 1
            print(output)
    elapsed = format(time.time() - started, '.1f')
    if failed:
        print('FAILED: ' + str(failed) + ' of ' + str(len(results)) + ' test folders (' + str(total) + ' tests run, ' + elapsed + 's)')
        return 1
    print('PASSED: ' + str(total) + ' tests in ' + str(len(results)) + ' folders (' + elapsed + 's)')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='BrisartOS command router. Python standard library only.')
    parser.add_argument('command', choices=sorted(list(COMMANDS) + ['test']))
    parser.add_argument('options', nargs=argparse.REMAINDER)
    arguments = parser.parse_args(argv)
    if arguments.command == 'test':
        return _run_tests(arguments.options)
    extra = arguments.options if arguments.command == 'start' else []
    return subprocess.call(INTERPRETER + COMMANDS[arguments.command] + extra, cwd=ROOT)


if __name__ == '__main__':
    raise SystemExit(main())
