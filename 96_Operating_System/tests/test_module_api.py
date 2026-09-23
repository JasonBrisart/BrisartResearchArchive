"""
tests/test_module_api.py

Purpose
-------
Unit tests for `brisartos/runtime/module_api.py` (`ModuleAPI`,
`PermissionError`, `ServiceUnavailableError`). `ModuleAPI` is the entire
trust boundary between a loaded module's own code and the unrestricted
`SystemAPI` / `ServiceRegistry` it wraps: every gated method must call
`self.require(...)` with the exact permission string a module declares in
its `MODULE_PERMISSIONS` tuple before delegating. These tests exist to
guarantee that boundary can never silently widen -- e.g. a future edit
that adds a new gated method but forgets the `self.require(...)` call
would otherwise go unnoticed until a module unexpectedly bypassed its own
declared permission set.

Communication relationships
----------------------------
- `brisartos/runtime/module_loader.LoadedModule.run()` constructs one
  `ModuleAPI` per module execution, seeded with that module's own
  `MODULE_PERMISSIONS` tuple -- see `tests/test_module_loader.py` for that
  integration path.
- `modules/hello_lab/module.py` is BrisartOS's one real, shipped module and
  declares `("log", "module_data", "object_id", "service:filesystem")`;
  `tests/test_hello_lab_module.py` exercises `ModuleAPI` through that
  module's actual permission set end-to-end. This file instead tests
  `ModuleAPI` directly, against fakes, so every gated method and every
  permission-denied path is covered independently of what `hello_lab`
  happens to use.

Settings / parameters
----------------------
- `ModuleAPI(module_name, permissions, system_api, service_registry=None)`:
  `permissions` is converted to a `set` internally, so duplicate or
  unordered input tuples behave identically. `service_registry` is
  optional and defaults to `None`; `get_service()` must raise
  `ServiceUnavailableError` (not `AttributeError`) if a module calls it
  with no registry attached, even if the module otherwise holds the
  correct `service:<name>` permission.
- Every gated method's required permission string is fixed by the source:
  `new_object_id` -> `"object_id"`, `log` -> `"log"`,
  `write_module_text`/`read_module_text`/`module_data_path` ->
  `"module_data"`, `get_platform_info` -> `"platform_info"`,
  `get_service(name)` -> `f"service:{name}"`.

Edge-case behavior
-------------------
- `PermissionError` raised by `require()` must include both the module's
  own name and the missing permission string in its message, since that
  message is the only diagnostic a lab operator sees when a module fails.
- `now_utc()` is the one delegated method that is **not** gated by any
  permission (it has no corresponding `self.require(...)` call in the
  source), so it must succeed regardless of a module's declared
  permissions.
- `available_services()` must return `[]` (not raise) when no
  `service_registry` is attached, and must return the registry's full
  name list regardless of which `service:<name>` permissions the calling
  module actually holds -- it is a diagnostics helper, not a gated
  accessor.
"""
import unittest
from unittest.mock import MagicMock

from _support import add_brisartos_runtime_to_syspath

add_brisartos_runtime_to_syspath()

from module_api import (  # noqa: E402
    ModuleAPI,
    PermissionError as ModulePermissionError,
    ServiceUnavailableError,
)


def make_fake_system_api():
    fake = MagicMock()
    fake.now_utc.return_value = "2026-08-29T00:00:00+00:00"
    fake.new_object_id.return_value = "deadbeefdeadbeefdeadbeefdeadbeef"
    fake.log.return_value = None
    fake.module_data_path.return_value = "/fake/module_data/hello_lab"
    fake.write_module_text.return_value = "/fake/module_data/hello_lab/x.txt"
    fake.read_module_text.return_value = "fake contents"
    fake.get_platform_info.return_value = {"os_name": "BrisartOS"}
    return fake


class ModuleAPIPermissionEnforcementTests(unittest.TestCase):
    def setUp(self):
        self.system_api = make_fake_system_api()

    def test_require_raises_for_missing_permission(self):
        api = ModuleAPI("hello_lab", (), self.system_api)
        with self.assertRaises(ModulePermissionError) as ctx:
            api.require("log")
        message = str(ctx.exception)
        self.assertIn("hello_lab", message)
        self.assertIn("log", message)

    def test_require_succeeds_for_granted_permission(self):
        api = ModuleAPI("hello_lab", ("log",), self.system_api)
        api.require("log")  # must not raise

    def test_new_object_id_requires_object_id_permission(self):
        api = ModuleAPI("hello_lab", (), self.system_api)
        with self.assertRaises(ModulePermissionError):
            api.new_object_id()
        self.system_api.new_object_id.assert_not_called()

    def test_new_object_id_delegates_when_permitted(self):
        api = ModuleAPI("hello_lab", ("object_id",), self.system_api)
        result = api.new_object_id()
        self.assertEqual(result, "deadbeefdeadbeefdeadbeefdeadbeef")
        self.system_api.new_object_id.assert_called_once()

    def test_log_requires_log_permission(self):
        api = ModuleAPI("hello_lab", (), self.system_api)
        with self.assertRaises(ModulePermissionError):
            api.log("hello_lab", "hi")
        self.system_api.log.assert_not_called()

    def test_log_delegates_when_permitted(self):
        api = ModuleAPI("hello_lab", ("log",), self.system_api)
        api.log("hello_lab", "hi")
        self.system_api.log.assert_called_once_with("hello_lab", "hi")

    def test_module_data_path_requires_module_data_permission(self):
        api = ModuleAPI("hello_lab", (), self.system_api)
        with self.assertRaises(ModulePermissionError):
            api.module_data_path("hello_lab")

    def test_write_module_text_requires_module_data_permission(self):
        api = ModuleAPI("hello_lab", (), self.system_api)
        with self.assertRaises(ModulePermissionError):
            api.write_module_text("hello_lab", "x.txt", "content")

    def test_write_module_text_delegates_when_permitted(self):
        api = ModuleAPI("hello_lab", ("module_data",), self.system_api)
        result = api.write_module_text("hello_lab", "x.txt", "content")
        self.assertEqual(result, "/fake/module_data/hello_lab/x.txt")
        self.system_api.write_module_text.assert_called_once_with(
            "hello_lab", "x.txt", "content"
        )

    def test_read_module_text_requires_module_data_permission(self):
        api = ModuleAPI("hello_lab", (), self.system_api)
        with self.assertRaises(ModulePermissionError):
            api.read_module_text("hello_lab", "x.txt")

    def test_read_module_text_delegates_when_permitted(self):
        api = ModuleAPI("hello_lab", ("module_data",), self.system_api)
        result = api.read_module_text("hello_lab", "x.txt")
        self.assertEqual(result, "fake contents")

    def test_get_platform_info_requires_platform_info_permission(self):
        api = ModuleAPI("hello_lab", (), self.system_api)
        with self.assertRaises(ModulePermissionError):
            api.get_platform_info()

    def test_get_platform_info_delegates_when_permitted(self):
        api = ModuleAPI("hello_lab", ("platform_info",), self.system_api)
        self.assertEqual(api.get_platform_info(), {"os_name": "BrisartOS"})

    def test_now_utc_is_not_permission_gated(self):
        api = ModuleAPI("hello_lab", (), self.system_api)
        result = api.now_utc()
        self.assertEqual(result, "2026-08-29T00:00:00+00:00")


class ModuleAPIServiceAccessTests(unittest.TestCase):
    def setUp(self):
        self.system_api = make_fake_system_api()

    def test_get_service_requires_service_specific_permission(self):
        registry = MagicMock()
        api = ModuleAPI(
            "hello_lab", (), self.system_api, service_registry=registry
        )
        with self.assertRaises(ModulePermissionError) as ctx:
            api.get_service("filesystem")
        self.assertIn("service:filesystem", str(ctx.exception))
        registry.get_service_object.assert_not_called()

    def test_get_service_raises_service_unavailable_with_no_registry(self):
        api = ModuleAPI(
            "hello_lab", ("service:filesystem",), self.system_api,
            service_registry=None,
        )
        with self.assertRaises(ServiceUnavailableError):
            api.get_service("filesystem")

    def test_get_service_raises_service_unavailable_when_not_registered(self):
        registry = MagicMock()
        registry.get_service_object.return_value = None
        api = ModuleAPI(
            "hello_lab", ("service:filesystem",), self.system_api,
            service_registry=registry,
        )
        with self.assertRaises(ServiceUnavailableError):
            api.get_service("filesystem")

    def test_get_service_returns_service_object_when_available(self):
        fake_service = object()
        registry = MagicMock()
        registry.get_service_object.return_value = fake_service
        api = ModuleAPI(
            "hello_lab", ("service:filesystem",), self.system_api,
            service_registry=registry,
        )
        self.assertIs(api.get_service("filesystem"), fake_service)
        registry.get_service_object.assert_called_once_with("filesystem")

    def test_available_services_returns_empty_list_with_no_registry(self):
        api = ModuleAPI("hello_lab", (), self.system_api, service_registry=None)
        self.assertEqual(api.available_services(), [])

    def test_available_services_ignores_permission_gating(self):
        """
        available_services() is a diagnostics helper: it must list every
        registered service name regardless of which service:<name>
        permissions this particular module happens to hold.
        """
        registry = MagicMock()
        registry.names.return_value = ["archive", "filesystem", "settings", "update"]
        api = ModuleAPI("hello_lab", (), self.system_api, service_registry=registry)
        self.assertEqual(
            api.available_services(),
            ["archive", "filesystem", "settings", "update"],
        )


class ModuleAPIPermissionSetTests(unittest.TestCase):
    def test_duplicate_permissions_in_input_tuple_are_deduplicated(self):
        api = ModuleAPI(
            "hello_lab", ("log", "log", "log"), make_fake_system_api()
        )
        self.assertEqual(api.permissions, {"log"})

    def test_permission_order_does_not_matter(self):
        api = ModuleAPI(
            "hello_lab", ("object_id", "log"), make_fake_system_api()
        )
        api.require("log")
        api.require("object_id")  # neither call should raise


if __name__ == "__main__":
    unittest.main()
