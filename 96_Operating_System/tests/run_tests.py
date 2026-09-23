"""
tests/run_tests.py

Purpose
-------
The single entry point for running the entire BrisartOS automated test
suite: `python tests/run_tests.py`. This exists because BrisartOS's
dependency policy (`docs/DEPENDENCY_POLICY.md`) rules out pytest or any
other third-party test runner, so this file wraps the standard library's
own `unittest` discovery and text runner instead -- no dependency beyond
Python itself, consistent with every other tool in this repository
(`tests/boot_sector_test.py`, `brisartos/boot/make_boot_image.py`, etc.).

Communication relationships
----------------------------
- Discovers and runs every `tests/test_*.py` module (via
  `unittest.TestLoader().discover(...)`), which in turn each import
  `tests/_support.py` for shared `sys.path`/working-directory setup before
  importing anything from `brisartos/`, `modules/`, or `version.py`. This
  file does not itself know about any individual test module; adding a new
  `tests/test_*.py` file is automatically picked up on the next run with
  no registration step required.
- `tests/_support.py` is explicitly excluded from discovery by
  `unittest`'s own `test_*.py` filename pattern (it is named `_support.py`,
  not `test_support.py`), so it never gets collected as if it contained
  tests itself.

Settings / parameters
----------------------
- No command-line arguments are required. Running `python
  tests/run_tests.py` (from any working directory) discovers and runs
  every test module inside the `tests/` directory that contains this
  file, using `top_level_dir` set explicitly to that same directory so
  discovery works correctly whether or not `tests/` happens to be on
  `sys.path` already.
- Exit code: `0` if every discovered test passes, `1` otherwise -- this is
  what makes the script usable as a CI/pre-commit gate (see
  `docs/CHANGELOG.md`'s and `README.md`'s roadmap entries for an
  automated test suite and CI pipeline) without any test-framework-
  specific plugin needed on the CI side.

Edge-case behavior
-------------------
- If `tests/` contains zero discoverable test modules (e.g. someone runs
  this against a stripped-down checkout), `unittest` reports "Ran 0 tests"
  and exits `0` -- this script does not treat an empty suite as a failure
  on its own, since that would make partial/filtered checkouts fail for a
  reason unrelated to actual test outcomes.
- Any import-time error in a discovered test module (for example, a typo
  that breaks a `from _support import ...` line) surfaces as a failed
  "test" named after the broken module, via `unittest`'s own
  `_FailedTest` mechanism, rather than silently skipping that file.
"""
import sys
import unittest
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent


def main() -> int:
    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=str(THIS_DIR),
        pattern="test_*.py",
        top_level_dir=str(THIS_DIR),
    )
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
