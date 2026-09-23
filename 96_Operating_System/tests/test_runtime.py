"""
tests/test_runtime.py

Purpose
-------
Integration tests for `brisartos/runtime/runtime.py` (`BrisartRuntime`),
the class that wires `PlatformInfo`, `SystemAPI`, `ServiceRegistry`, and
`ModuleLoader` together into the one object `brisartos/shell/shell.py`
drives interactively. Unlike the other test files in this suite, these
tests deliberately exercise the real, shipped `modules/hello_lab/` module
end-to-end (copied into an isolated temporary working directory) rather
than a synthetic fixture, because `BrisartRuntime.boot()` is the actual
code path that discovers and would run it in production.

Communication relationships
----------------------------
- `BrisartRuntime.__init__` constructs `PlatformInfo`, `SystemAPI`, and
  `ServiceRegistry` itself (see `tests/test_platform_info.py`,
  `tests/test_system_api.py`, and `tests/test_service_registry.py` for
  each of those in isolation), then hands `SystemAPI` and `ServiceRegistry`
  to a `ModuleLoader` pointed at the hardcoded relative path `"modules"`
  (see `tests/test_module_loader.py` for `ModuleLoader` in isolation).
- `boot()` is the one method that has to run in a specific order:
  `register_builtin_services()` before `loader.discover()`, so that any
  module whose `run(api)` calls `api.get_service(...)` finds services
  already registered -- `modules/hello_lab/module.py` does exactly this.

Settings / parameters
----------------------
- `BrisartRuntime()` takes no constructor arguments; every dependency it
  builds is fixed by source (relative `"modules"` path, `SystemAPI`'s
  `Path.cwd()`-relative `module_data/`/`logs/`). Every test in this file
  therefore runs inside `_support.IsolatedCwd`, with a `modules/hello_lab/`
  folder copied in from the real repository so `loader.discover()` has
  something real to find.
- `describe_module(name)` / `describe_service(name)` / `run_module(name)`
  all print `"module not found"` / `"service not found"` and return
  `None` for an unknown name rather than raising -- this is what lets the
  interactive shell in `brisartos/shell/shell.py` handle a mistyped
  command name gracefully instead of crashing the whole session.

Edge-case behavior
-------------------
- `version_text()` must embed both `BrisartRuntime.NAME` and
  `BrisartRuntime.VERSION` (sourced from the single `version.py` source of
  truth at the repo root), matching the project's stated "single source
  of truth" versioning convention documented in `docs/CHANGELOG.md`'s
  0.4.1-alpha entry.
- `reload_modules()` must pick up a module added to `modules/` after the
  initial `boot()` call, without needing a fresh `BrisartRuntime` instance.
- Calling `describe_module`, `describe_service`, or `run_module` for an
  unknown name must not raise, matching the "not found" contract every
  other lookup-by-name method in this codebase follows (`ServiceRegistry`,
  `ModuleLoader`).
"""
import shutil
import unittest
from contextlib import redirect_stdout
from io import StringIO

from _support import (
    IsolatedCwd,
    MODULES_DIR,
    add_brisartos_runtime_to_syspath,
    add_repo_root_to_syspath,
)

# runtime.py itself does `from version import ...`, resolving version.py
# at the repo root via a flat import. That only works if the repo root is
# already on sys.path -- true in normal BrisartOS usage only because the
# process's cwd (implicitly on sys.path) happens to be the repo root.
# Since these tests may run from tests/ as cwd, the repo root must be
# added explicitly here before importing runtime.
add_repo_root_to_syspath()
add_brisartos_runtime_to_syspath()

from runtime import BrisartRuntime  # noqa: E402


def _install_hello_lab_module(target_modules_dir):
    """
    Copy the real, shipped modules/hello_lab/ folder into a fresh
    temporary `modules/` directory so BrisartRuntime.boot() has an actual
    production module to discover, rather than a synthetic fixture.
    """
    target_modules_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        MODULES_DIR / "hello_lab",
        target_modules_dir / "hello_lab",
    )


def _quiet_boot(runtime):
    """
    Call runtime.boot() with its banner output swallowed. BrisartRuntime
    has no "quiet mode" of its own -- boot() unconditionally prints a
    banner -- so tests that don't care about that console output redirect
    it here to keep `-v` test-runner output readable.
    """
    with redirect_stdout(StringIO()):
        runtime.boot()


class BrisartRuntimeBootTests(unittest.TestCase):
    def test_boot_registers_all_builtin_services(self):
        with IsolatedCwd() as tmp_dir:
            _install_hello_lab_module(tmp_dir / "modules")
            runtime = BrisartRuntime()
            _quiet_boot(runtime)
            self.assertEqual(
                runtime.services.names(),
                ["archive", "filesystem", "settings", "update"],
            )

    def test_boot_discovers_hello_lab_module(self):
        with IsolatedCwd() as tmp_dir:
            _install_hello_lab_module(tmp_dir / "modules")
            runtime = BrisartRuntime()
            _quiet_boot(runtime)
            self.assertIn("hello_lab", runtime.loader.modules)

    def test_version_text_contains_name_and_version(self):
        with IsolatedCwd() as tmp_dir:
            _install_hello_lab_module(tmp_dir / "modules")
            runtime = BrisartRuntime()
            text = runtime.version_text()
            self.assertIn(runtime.NAME, text)
            self.assertIn(runtime.VERSION, text)


class BrisartRuntimeModuleLifecycleTests(unittest.TestCase):
    def test_run_module_executes_hello_lab_end_to_end(self):
        with IsolatedCwd() as tmp_dir:
            _install_hello_lab_module(tmp_dir / "modules")
            runtime = BrisartRuntime()
            _quiet_boot(runtime)
            with redirect_stdout(StringIO()):
                runtime.run_module("hello_lab")
            # hello_lab's run() writes both a direct SystemAPI file and a
            # FilesystemService-mediated file; both must exist afterward.
            direct_file = tmp_dir / "module_data" / "hello_lab" / "hello.txt"
            service_file = tmp_dir / "module_data" / "hello_lab" / "service_demo.txt"
            self.assertTrue(direct_file.exists())
            self.assertTrue(service_file.exists())

    def test_run_module_unknown_name_prints_not_found_and_does_not_raise(self):
        with IsolatedCwd() as tmp_dir:
            _install_hello_lab_module(tmp_dir / "modules")
            runtime = BrisartRuntime()
            _quiet_boot(runtime)
            buffer = StringIO()
            with redirect_stdout(buffer):
                runtime.run_module("does_not_exist")
            self.assertIn("module not found", buffer.getvalue())

    def test_describe_module_unknown_name_prints_not_found(self):
        with IsolatedCwd() as tmp_dir:
            _install_hello_lab_module(tmp_dir / "modules")
            runtime = BrisartRuntime()
            _quiet_boot(runtime)
            buffer = StringIO()
            with redirect_stdout(buffer):
                runtime.describe_module("does_not_exist")
            self.assertIn("module not found", buffer.getvalue())

    def test_describe_module_known_name_prints_metadata(self):
        with IsolatedCwd() as tmp_dir:
            _install_hello_lab_module(tmp_dir / "modules")
            runtime = BrisartRuntime()
            _quiet_boot(runtime)
            buffer = StringIO()
            with redirect_stdout(buffer):
                runtime.describe_module("hello_lab")
            output = buffer.getvalue()
            self.assertIn("Hello Lab Module", output)
            self.assertIn("Jason Brisart", output)

    def test_reload_modules_picks_up_newly_added_module(self):
        with IsolatedCwd() as tmp_dir:
            modules_dir = tmp_dir / "modules"
            modules_dir.mkdir(parents=True, exist_ok=True)
            runtime = BrisartRuntime()
            _quiet_boot(runtime)
            self.assertEqual(runtime.loader.modules, {})
            _install_hello_lab_module(modules_dir)
            with redirect_stdout(StringIO()):
                runtime.reload_modules()
            self.assertIn("hello_lab", runtime.loader.modules)


class BrisartRuntimeServiceLifecycleTests(unittest.TestCase):
    def test_describe_service_unknown_name_prints_not_found(self):
        with IsolatedCwd() as tmp_dir:
            _install_hello_lab_module(tmp_dir / "modules")
            runtime = BrisartRuntime()
            _quiet_boot(runtime)
            buffer = StringIO()
            with redirect_stdout(buffer):
                runtime.describe_service("does_not_exist")
            self.assertIn("service not found", buffer.getvalue())

    def test_describe_service_known_name_prints_metadata(self):
        with IsolatedCwd() as tmp_dir:
            _install_hello_lab_module(tmp_dir / "modules")
            runtime = BrisartRuntime()
            _quiet_boot(runtime)
            buffer = StringIO()
            with redirect_stdout(buffer):
                runtime.describe_service("filesystem")
            output = buffer.getvalue()
            self.assertIn("Filesystem Service", output)
            self.assertIn("Online", output)


if __name__ == "__main__":
    unittest.main()
