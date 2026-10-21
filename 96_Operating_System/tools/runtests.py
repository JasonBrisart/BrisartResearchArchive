r"""
File: tools/runtests.py

Purpose
-------
Discover the BrisartOS test folders, run each in its own child interpreter
concurrently and print one result line per folder with a combined summary.

Public interface:
- run_tests(filters=()) -- Run every discovered test folder whose path contains
  one of the filters, or every folder when none are given, and return the exit
  status.
- main(argv=None) -- Treat the arguments as path-substring filters, run the
  tests and return the exit status; python run.py test calls this.

Design notes:

Test folders are tests/, each brisartos/*/tests and tools/tests. Each folder
runs unittest discovery in a separate child process with the same executable
and the -B and -S flags, up to eight at a time, so a failing import in one
folder cannot affect another. The reported test count comes from each child
unittest summary line. This file moved here from run.py so the root router is
only a routing table. tools/tests/test_tools.py runs it on temporary project
copies; those subprocess runs are not static imports.

Communication / relationships
-----------------------------
Standard library: concurrent, pathlib, subprocess, sys, time.
Imported by:
- run.py
Covered by tests: none directly.

Settings / parameters
---------------------
- ROOT = Path(__file__).resolve().parents[1] -- The project root, derived from
  this file location rather than the working directory.
- INTERPRETER = [sys.executable, '-B', '-S'] -- The executable and flags used
  for every child process.
- MAX_WORKERS = 8 -- The most test folders run at the same time.

Edge cases
----------
A filter that matches no folder prints a message and returns 2. A failing
folder prints its captured output and makes the run return 1; otherwise the
status is 0.

Known limitations
-----------------
- Test folders run in separate processes, so the printed total counts only
  folders that ran.
- Filters are path substrings, not patterns; the filter tests matches every
  test folder.
- A child that crashes before printing a unittest summary line contributes a
  count of zero.

Examples
--------
Run from the repository root.

::

    python -B run.py test
    python -B run.py test kernel shell
    python -B tools/runtests.py common
"""
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTERPRETER = [sys.executable, '-B', '-S']
MAX_WORKERS = 8


def _test_folders():
    found = [ROOT / 'tests'] + sorted(ROOT.glob('brisartos/*/tests')) + sorted(ROOT.glob('tools/tests'))
    return [folder for folder in found if folder.is_dir()]


def _run_folder(folder):
    started = time.time()
    result = subprocess.run(INTERPRETER + ['-m', 'unittest', 'discover', '-s', str(folder)],
                            cwd=ROOT, capture_output=True, text=True)
    output = result.stderr + result.stdout
    count = 0
    for line in output.splitlines():
        if line.startswith('Ran '):
            count = int(line.split()[1])
    return folder, result.returncode, count, time.time() - started, output


def run_tests(filters=()):
    folders = [folder for folder in _test_folders()
               if not filters or any(item in folder.relative_to(ROOT).as_posix() for item in filters)]
    if not folders:
        print('no test folders match ' + ' '.join(filters))
        return 2
    started = time.time()
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(folders))) as pool:
        results = list(pool.map(_run_folder, folders))
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
    argv = sys.argv[1:] if argv is None else list(argv)
    return run_tests(argv)


if __name__ == '__main__':
    raise SystemExit(main())
