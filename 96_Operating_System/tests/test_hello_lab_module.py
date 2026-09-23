"""
tests/test_hello_lab_module.py

Purpose
-------
Integration tests for `modules/hello_lab/module.py`, BrisartOS's one
shipped, real (non-fixture) module. Where `tests/test_module_loader.py`
exercises the discovery/ABI-gate/run lifecycle against synthetic modules,
and `tests/test_module_api.py` exercises `ModuleAPI`'s permission
enforcement against a fully mocked `SystemAPI`, this file wires the real
`hello_lab` module against real `SystemAPI` and `FilesystemService`
instances (backed by a temporary directory) to confirm the whole
permission-declared-in-`MODULE_PERMISSIONS` -> `ModuleAPI` ->
`SystemAPI`/`FilesystemService` chain actually holds together end-to-end
for the one module a lab operator would actually run today.

Communication relationships
----------------------------
- `hello_lab.run(api)` calls, in order: `api.new_object_id()` (requires
  `"object_id"`), `api.write_module_text(...)` (requires `"module_data"`),
  `api.log(...)` (requires `"log"`), `api.get_service("filesystem")`
  (requires `"service:filesystem"`), then `fs.write_text(...)` and
  `fs.list_files(...)` directly on the returned `FilesystemService`
  (service-level calls, not further gated by `ModuleAPI` once obtained).
- `MODULE_PERMISSIONS = ("log", "module_data", "object_id",
  "service:filesystem")` is the exact tuple `ModuleLoader` reads off the
  module and forwards into the `ModuleAPI` it constructs inside
  `LoadedModule.run()` (see `tests/test_module_loader.py`); this file
  additionally proves that removing any one of those four permissions
  causes `hello_lab.run()` to fail with `PermissionError` at the specific
  call site that needed it, rather than somewhere unrelated.

Settings / parameters
----------------------
- `hello_lab.run(api)` takes a single `api` argument satisfying the
  `ModuleAPI` interface; this file always constructs a real `ModuleAPI`
  wrapping a real `SystemAPI` (isolated under `_support.IsolatedCwd`, since
  `SystemAPI` writes to `Path.cwd()`) and a real `ServiceRegistry` with
  only the `FilesystemService` registered (the one service `hello_lab`
  actually uses).
- `MODULE_NAME` is the fixed string `"hello_lab"`, which is also the
  literal module name `run()` passes to `write_module_text`,
  `get_service`, and `fs.write_text`/`fs.list_files` -- all four call
  sites must agree on this name for the module's own files to end up in
  the same `module_data/hello_lab/` directory.

Edge-case behavior
-------------------
- With the full permission tuple granted, `run()` must produce both
  `module_data/hello_lab/hello.txt` (written via the raw `SystemAPI` path)
  and `module_data/hello_lab/service_demo.txt` (written via the
  `FilesystemService` path), each containing the same freshly generated
  object ID, proving both write paths converge on the same identifier
  rather than each independently regenerating one.
- Removing `"object_id"` must raise `PermissionError` before any file is
  written at all (the very first line of `run()` calls
  `api.new_object_id()`).
- Removing `"service:filesystem"` must raise `PermissionError` only after
  the direct `SystemAPI` file (`hello.txt`) has already been written,
  since that write happens earlier in `run()` than the
  `api.get_service("filesystem")` call.
"""
import unittest
from contextlib import redirect_stdout
from io import StringIO

from _support import (
    IsolatedCwd,
    add_brisartos_runtime_to_syspath,
    add_brisartos_services_to_syspath,
    add_repo_root_to_syspath,
    load_module_from_path,
)

add_repo_root_to_syspath()
add_brisartos_runtime_to_syspath()
add_brisartos_services_to_syspath()

from brisart_platform import PlatformInfo  # noqa: E402
from module_api import ModuleAPI, PermissionError as ModulePermissionError  # noqa: E402
from system_api import SystemAPI  # noqa: E402
from service_registry import ServiceRegistry  # noqa: E402

hello_lab = load_module_from_path(
    "brisartos_hello_lab_module", "modules/hello_lab/module.py"
)

FULL_PERMISSIONS = hello_lab.MODULE_PERMISSIONS


def _run_quietly(api):
    """
    hello_lab.run() prints its progress unconditionally (there is no
    quiet/verbose flag on the module itself); tests that don't assert on
    that console output redirect it here to keep -v test-runner output
    readable.
    """
    with redirect_stdout(StringIO()):
        hello_lab.run(api)


def _build_module_api(permissions, tmp_dir):
    system_api = SystemAPI(PlatformInfo())
    registry = ServiceRegistry(module_data_root=system_api.module_data_root)
    registry.register_builtin_services()
    return ModuleAPI(
        module_name=hello_lab.MODULE_NAME,
        permissions=permissions,
        system_api=system_api,
        service_registry=registry,
    )


class HelloLabModuleMetadataTests(unittest.TestCase):
    def test_declares_expected_permission_tuple(self):
        self.assertEqual(
            set(hello_lab.MODULE_PERMISSIONS),
            {"log", "module_data", "object_id", "service:filesystem"},
        )

    def test_declares_supported_abi(self):
        self.assertEqual(hello_lab.MODULE_ABI, "brisartos.module.v1")


class HelloLabModuleFullPermissionRunTests(unittest.TestCase):
    def test_run_writes_both_direct_and_service_files_with_matching_object_id(self):
        with IsolatedCwd() as tmp_dir:
            api = _build_module_api(FULL_PERMISSIONS, tmp_dir)
            _run_quietly(api)

            direct_file = tmp_dir / "module_data" / "hello_lab" / "hello.txt"
            service_file = tmp_dir / "module_data" / "hello_lab" / "service_demo.txt"
            self.assertTrue(direct_file.exists())
            self.assertTrue(service_file.exists())

            direct_content = direct_file.read_text(encoding="utf-8")
            service_content = service_file.read_text(encoding="utf-8")
            self.assertIn("Object ID:", direct_content)
            self.assertIn("Object ID:", service_content)

            direct_object_id = direct_content.strip().splitlines()[-1].split(": ")[-1]
            service_object_id = service_content.strip().splitlines()[-1].split(": ")[-1]
            self.assertEqual(direct_object_id, service_object_id)

    def test_run_logs_module_executed(self):
        with IsolatedCwd() as tmp_dir:
            api = _build_module_api(FULL_PERMISSIONS, tmp_dir)
            _run_quietly(api)
            log_file = tmp_dir / "logs" / "hello_lab.log"
            self.assertTrue(log_file.exists())
            self.assertIn("module executed", log_file.read_text(encoding="utf-8"))


class HelloLabModulePermissionDenialTests(unittest.TestCase):
    def test_missing_object_id_permission_fails_before_any_write(self):
        with IsolatedCwd() as tmp_dir:
            permissions = tuple(p for p in FULL_PERMISSIONS if p != "object_id")
            api = _build_module_api(permissions, tmp_dir)
            with self.assertRaises(ModulePermissionError):
                _run_quietly(api)
            # SystemAPI.__init__ itself always creates the top-level
            # module_data/ directory as a side effect of construction, so
            # this checks for the module's own file specifically rather
            # than asserting module_data/ itself is absent.
            direct_file = tmp_dir / "module_data" / "hello_lab" / "hello.txt"
            self.assertFalse(direct_file.exists())

    def test_missing_module_data_permission_fails_before_direct_write(self):
        with IsolatedCwd() as tmp_dir:
            permissions = tuple(p for p in FULL_PERMISSIONS if p != "module_data")
            api = _build_module_api(permissions, tmp_dir)
            with self.assertRaises(ModulePermissionError):
                _run_quietly(api)
            direct_file = tmp_dir / "module_data" / "hello_lab" / "hello.txt"
            self.assertFalse(direct_file.exists())

    def test_missing_service_filesystem_permission_fails_after_direct_write(self):
        with IsolatedCwd() as tmp_dir:
            permissions = tuple(p for p in FULL_PERMISSIONS if p != "service:filesystem")
            api = _build_module_api(permissions, tmp_dir)
            with self.assertRaises(ModulePermissionError):
                _run_quietly(api)
            # The direct SystemAPI write happens before the gated
            # get_service() call, so it must have already succeeded.
            direct_file = tmp_dir / "module_data" / "hello_lab" / "hello.txt"
            self.assertTrue(direct_file.exists())
            # But the FilesystemService-mediated file must never be written.
            service_file = tmp_dir / "module_data" / "hello_lab" / "service_demo.txt"
            self.assertFalse(service_file.exists())

    def test_missing_log_permission_raises_permission_error(self):
        with IsolatedCwd() as tmp_dir:
            permissions = tuple(p for p in FULL_PERMISSIONS if p != "log")
            api = _build_module_api(permissions, tmp_dir)
            with self.assertRaises(ModulePermissionError):
                _run_quietly(api)


if __name__ == "__main__":
    unittest.main()
