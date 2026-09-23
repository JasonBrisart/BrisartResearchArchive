"""
tests/_support.py

Purpose
-------
Shared, dependency-free test scaffolding for the BrisartOS automated test
suite. This file is not itself a test module (it holds no TestCase classes
and matches no `test_*.py` discovery pattern), so `unittest discover` and
`tests/run_tests.py` both skip it automatically. Every other file under
tests/ imports from here instead of duplicating path/setup logic.

Why this file exists
---------------------
BrisartOS is not laid out as an installable Python package (there is no
top-level `brisartos/__init__.py`, and most modules import each other with
flat, non-relative imports, e.g. `brisartos/runtime/module_loader.py` does
`from module_api import ModuleAPI` rather than a package-qualified import).
This is a deliberate consequence of the project's current, pre-packaging
layout, not something this test suite should silently work around by
changing production files. Instead, this helper reproduces, for tests, the
exact same `sys.path` shape that `brisartos/runtime/runtime.py` already
sets up for itself at import time, so that importing each module under test
behaves identically to how it behaves when BrisartOS actually runs.

Communication relationships
----------------------------
- Every `tests/test_*.py` module imports `REPO_ROOT` and one or more of the
  `add_*_to_syspath()` helpers (or `load_module_from_path()`) from this file
  before importing anything from `brisartos/`, `modules/`, or `version.py`.
- `IsolatedCwd` is used by any test that instantiates `SystemAPI` (directly
  or indirectly through `BrisartRuntime`), because `SystemAPI.__init__`
  unconditionally creates `module_data/` and `logs/` directories relative to
  `Path.cwd()`. Without isolating the working directory, running the test
  suite would create and pollute those directories inside the real
  repository checkout.

Settings / parameters
----------------------
- `REPO_ROOT`: absolute path to the BrisartOS repository root, computed as
  the parent of the `tests/` directory. Every other path in this file is
  derived from it so the suite works regardless of the caller's own cwd.
- `add_repo_root_to_syspath()`: adds `REPO_ROOT` itself, needed for
  `import version` and for `from brisartos.apps import browser`  (the
  latter relies on `brisartos/` being resolved as an implicit namespace
  package, since it has no `__init__.py` of its own).
- `add_brisartos_dir_to_syspath()`: adds `brisartos/` itself, needed for
  flat imports of modules that live directly inside it, such as
  `brisartos/emitter.py` and `brisartos/labels.py`.
- `add_brisartos_runtime_to_syspath()`: adds `brisartos/runtime/`, needed
  for the flat imports used inside `runtime.py`, `module_loader.py`,
  `module_api.py`, `system_api.py`, and `brisart_platform.py`.
- `add_brisartos_services_to_syspath()`: adds `brisartos/services/`, needed
  for the flat imports used inside `service_registry.py` and its four
  built-in services.
- `load_module_from_path(alias, relative_path)`: loads a single file as a
  module under a private `alias` via `importlib.util`, without adding its
  directory to `sys.path` and without touching `sys.modules[stdlib_name]`.
  This is used for `brisartos/platform.py`, because Python's standard
  library already ships a module literally named `platform`
  (`Lib/platform.py`). If `brisartos/` were added to `sys.path` and code
  elsewhere did a plain `import platform` expecting the standard library
  module, it could silently receive BrisartOS's `platform.py` instead (or
  vice versa, depending on import order and caching). Loading it by exact
  file path under a private alias sidesteps that ambiguity entirely rather
  than relying on import order to save us.
  This same helper is also used for `tests/boot_sector_test.py`, for an
  analogous reason discovered while building this suite: some Python
  environments have a third-party or site-installed package literally
  named `tests` (unrelated to this repository's `tests/` directory), which
  can shadow a package-qualified `from tests import boot_sector_test` and
  raise a confusing `ImportError` depending on `sys.path` ordering.
  Loading `boot_sector_test.py` by exact file path avoids depending on
  `tests/` resolving as a namespace package at all.

Edge-case behavior
-------------------
- All `add_*_to_syspath()` helpers are idempotent: calling them multiple
  times (once per test module, across a full `discover` run) does not
  create duplicate `sys.path` entries.
- `IsolatedCwd` restores the original working directory on exit even if the
  wrapped test body raises, and it points `Path.cwd()` at a fresh
  `tempfile.TemporaryDirectory()` that is deleted on exit, so no BrisartOS
  test ever leaves `module_data/` or `logs/` artifacts on disk.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BRISARTOS_DIR = REPO_ROOT / "brisartos"
RUNTIME_DIR = BRISARTOS_DIR / "runtime"
SERVICES_DIR = BRISARTOS_DIR / "services"
BOOT_DIR = BRISARTOS_DIR / "boot"
MODULES_DIR = REPO_ROOT / "modules"
TESTS_DIR = REPO_ROOT / "tests"


def _insert_once(path: Path) -> None:
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)


def add_repo_root_to_syspath() -> None:
    _insert_once(REPO_ROOT)


def add_brisartos_dir_to_syspath() -> None:
    _insert_once(BRISARTOS_DIR)


def add_brisartos_runtime_to_syspath() -> None:
    _insert_once(RUNTIME_DIR)


def add_brisartos_services_to_syspath() -> None:
    _insert_once(SERVICES_DIR)


def add_brisartos_boot_to_syspath() -> None:
    _insert_once(BOOT_DIR)


def load_module_from_path(alias: str, relative_path: str):
    """
    Load the file at `REPO_ROOT / relative_path` as a module registered
    under the private name `alias`, bypassing `sys.path` entirely.

    `alias` should be a name that cannot collide with a real importable
    module elsewhere in the process (this test suite uses names like
    "brisartos_platform_module" for exactly this reason). Returns the
    loaded module object; also leaves it registered in `sys.modules[alias]`
    so repeated calls with the same alias return a fresh reload rather than
    accumulating orphaned module objects.
    """
    full_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(alias, full_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load module spec for {full_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module


class IsolatedCwd:
    """
    Context manager that chdir()s into a fresh temporary directory for the
    duration of the `with` block and always restores the original working
    directory afterward, even on exception.

    Use this around any test that constructs `SystemAPI` (directly, or
    indirectly via `BrisartRuntime`), since `SystemAPI.__init__` creates
    `module_data/` and `logs/` relative to `Path.cwd()` with no way to
    override that location through a constructor argument.
    """

    def __init__(self):
        self._tmp = None
        self._previous_cwd = None

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._previous_cwd = os.getcwd()
        os.chdir(self._tmp.name)
        return Path(self._tmp.name)

    def __exit__(self, exc_type, exc_value, traceback):
        os.chdir(self._previous_cwd)
        self._tmp.cleanup()
        return False
