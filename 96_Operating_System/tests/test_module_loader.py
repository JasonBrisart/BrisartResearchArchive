"""
tests/test_module_loader.py

Purpose
-------
Unit and integration tests for `brisartos/runtime/module_loader.py`
(`LoadedModule`, `ModuleLoader`). This is the code that turns a
`modules/<name>/module.py` file on disk into a live, runnable module
object, and it is deliberately forgiving about individual module
failures (`discover()` catches broad `Exception` per-folder so one broken
module cannot take down the whole runtime). These tests build small,
throwaway module folders under a temporary `modules/` directory -- never
the real `modules/hello_lab/` -- to exercise the full discovery/load/ABI
gate/run lifecycle without depending on (or risking mutating) the
repository's one shipped module.

Communication relationships
----------------------------
- `BrisartRuntime.__init__` (`runtime.py`) constructs one `ModuleLoader`
  pointed at the literal relative path `"modules"` and calls
  `discover()` during `boot()` -- see `tests/test_runtime.py` for that
  integration path against the real `modules/hello_lab/`.
- `LoadedModule.run()` constructs a fresh `ModuleAPI` (tested in isolation
  in `tests/test_module_api.py`) from the loaded module's own
  `MODULE_PERMISSIONS`, then calls `self.api.log(...)` **directly on the
  raw SystemAPI**, bypassing the permission wrapper, before and after
  invoking `module_object.run(module_api)`. This file explicitly tests
  that bypass: a module with zero declared permissions can still be
  "started"/"finished" logged by the framework even though its own
  `run(api)` body would be denied if it tried to call `api.log(...)`
  itself.

Settings / parameters
----------------------
- `ModuleLoader(modules_path, api, service_registry=None)`: `modules_path`
  is coerced to a `Path` and created (via `discover()`) if it does not
  already exist -- tests use a fresh `tempfile.TemporaryDirectory()` for
  this on every run so no test ever touches the real `modules/` folder.
- `ModuleLoader.SUPPORTED_ABI` is the fixed string `"brisartos.module.v1"`;
  any discovered `module.py` whose `MODULE_ABI` does not match exactly is
  skipped (printed, not raised) during `discover()`.
- A valid module file must define, at minimum: `MODULE_NAME`,
  `MODULE_DISPLAY_NAME`, `MODULE_VERSION`, `MODULE_AUTHOR`,
  `MODULE_DESCRIPTION`, `MODULE_ABI`, `MODULE_PERMISSIONS`, and a
  module-level `run(api)` function.

Edge-case behavior
-------------------
- A folder under `modules_path` with no `module.py` inside it must be
  silently skipped by `discover()` (not an error).
- A `module.py` that raises during import (e.g. a `SyntaxError` or a
  missing required attribute like `MODULE_NAME`) must be caught, printed,
  and skipped -- `discover()` must still successfully load every *other*
  valid module in the same directory.
- A `module.py` with a mismatched `MODULE_ABI` must be skipped the same
  way, and must **not** appear in `loader.modules` afterward.
- `ModuleLoader.get(name)` for a name that was never discovered (or that
  failed to load) must return `None`, matching the same "not found"
  contract `ServiceRegistry.get()` uses.
"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from _support import add_brisartos_runtime_to_syspath

add_brisartos_runtime_to_syspath()

from module_loader import ModuleLoader  # noqa: E402


GOOD_MODULE_SOURCE = '''
MODULE_NAME = "good_module"
MODULE_DISPLAY_NAME = "Good Module"
MODULE_VERSION = "1.0.0"
MODULE_AUTHOR = "Test Author"
MODULE_DESCRIPTION = "A well-formed test module."
MODULE_ABI = "brisartos.module.v1"
MODULE_PERMISSIONS = ()

RAN = []

def run(api):
    RAN.append(api.module_name)
'''

WRONG_ABI_MODULE_SOURCE = '''
MODULE_NAME = "wrong_abi_module"
MODULE_DISPLAY_NAME = "Wrong ABI Module"
MODULE_VERSION = "1.0.0"
MODULE_AUTHOR = "Test Author"
MODULE_DESCRIPTION = "Declares an unsupported ABI."
MODULE_ABI = "brisartos.module.v2-does-not-exist"
MODULE_PERMISSIONS = ()

def run(api):
    pass
'''

BROKEN_MODULE_SOURCE = '''
raise RuntimeError("this module fails to import on purpose")
'''

PERMISSIONLESS_LOG_ATTEMPT_SOURCE = '''
MODULE_NAME = "permissionless_module"
MODULE_DISPLAY_NAME = "Permissionless Module"
MODULE_VERSION = "1.0.0"
MODULE_AUTHOR = "Test Author"
MODULE_DESCRIPTION = "Declares no permissions at all."
MODULE_ABI = "brisartos.module.v1"
MODULE_PERMISSIONS = ()

CALLED = []

def run(api):
    CALLED.append(True)
'''


class ModuleLoaderTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.modules_path = Path(self._tmp.name) / "modules"
        self.modules_path.mkdir()
        self.fake_api = MagicMock()

    def tearDown(self):
        self._tmp.cleanup()

    def _write_module(self, folder_name, source):
        folder = self.modules_path / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "module.py").write_text(source, encoding="utf-8")
        return folder


class ModuleLoaderDiscoveryTests(ModuleLoaderTestCase):
    def test_discover_loads_a_well_formed_module(self):
        self._write_module("good_module", GOOD_MODULE_SOURCE)
        loader = ModuleLoader(self.modules_path, self.fake_api)
        loader.discover()
        self.assertIn("good_module", loader.modules)
        module = loader.get("good_module")
        self.assertEqual(module.display_name, "Good Module")
        self.assertEqual(module.version, "1.0.0")
        self.assertEqual(module.permissions, ())

    def test_discover_creates_modules_path_if_missing(self):
        shutil.rmtree(self.modules_path)
        loader = ModuleLoader(self.modules_path, self.fake_api)
        loader.discover()
        self.assertTrue(self.modules_path.exists())
        self.assertEqual(loader.modules, {})

    def test_folder_without_module_py_is_skipped(self):
        (self.modules_path / "not_a_module").mkdir()
        loader = ModuleLoader(self.modules_path, self.fake_api)
        loader.discover()
        self.assertEqual(loader.modules, {})

    def test_file_at_modules_path_top_level_is_ignored(self):
        (self.modules_path / "stray_file.txt").write_text("not a folder", encoding="utf-8")
        loader = ModuleLoader(self.modules_path, self.fake_api)
        loader.discover()  # must not raise
        self.assertEqual(loader.modules, {})

    def test_mismatched_abi_module_is_skipped(self):
        self._write_module("wrong_abi_module", WRONG_ABI_MODULE_SOURCE)
        loader = ModuleLoader(self.modules_path, self.fake_api)
        loader.discover()
        self.assertNotIn("wrong_abi_module", loader.modules)

    def test_module_that_raises_on_import_is_skipped_without_crashing_discovery(self):
        self._write_module("broken_module", BROKEN_MODULE_SOURCE)
        self._write_module("good_module", GOOD_MODULE_SOURCE)
        loader = ModuleLoader(self.modules_path, self.fake_api)
        loader.discover()  # must not raise despite the broken module
        self.assertNotIn("broken_module", loader.modules)
        self.assertIn("good_module", loader.modules)

    def test_get_returns_none_for_unknown_module(self):
        loader = ModuleLoader(self.modules_path, self.fake_api)
        loader.discover()
        self.assertIsNone(loader.get("never_existed"))

    def test_rediscover_reflects_newly_added_module(self):
        loader = ModuleLoader(self.modules_path, self.fake_api)
        loader.discover()
        self.assertEqual(loader.modules, {})
        self._write_module("good_module", GOOD_MODULE_SOURCE)
        loader.discover()
        self.assertIn("good_module", loader.modules)


class LoadedModuleRunTests(ModuleLoaderTestCase):
    def test_run_calls_module_run_with_a_module_api(self):
        self._write_module("good_module", GOOD_MODULE_SOURCE)
        loader = ModuleLoader(self.modules_path, self.fake_api)
        loader.discover()
        module = loader.get("good_module")
        module.run()
        self.assertEqual(module.module_object.RAN, ["good_module"])

    def test_run_logs_started_and_finished_via_raw_system_api(self):
        """
        LoadedModule.run() logs "module started"/"module finished" by
        calling self.api.log(...) directly -- the raw SystemAPI, not the
        permission-gated ModuleAPI -- even for a module that declares zero
        permissions of its own. This confirms that framework-level
        lifecycle logging is not subject to the module's own permission
        grant.
        """
        self._write_module("permissionless_module", PERMISSIONLESS_LOG_ATTEMPT_SOURCE)
        loader = ModuleLoader(self.modules_path, self.fake_api)
        loader.discover()
        module = loader.get("permissionless_module")
        module.run()
        self.fake_api.log.assert_any_call("permissionless_module", "module started")
        self.fake_api.log.assert_any_call("permissionless_module", "module finished")
        self.assertEqual(module.module_object.CALLED, [True])

    def test_run_passes_service_registry_through_to_module_api(self):
        self._write_module("good_module", GOOD_MODULE_SOURCE)
        fake_registry = MagicMock()
        loader = ModuleLoader(
            self.modules_path, self.fake_api, service_registry=fake_registry
        )
        loader.discover()
        module = loader.get("good_module")
        # module.run() doesn't expose the ModuleAPI it builds internally,
        # so we confirm wiring by checking the loader/LoadedModule kept a
        # reference to the same registry object passed at construction.
        self.assertIs(module.service_registry, fake_registry)


if __name__ == "__main__":
    unittest.main()
