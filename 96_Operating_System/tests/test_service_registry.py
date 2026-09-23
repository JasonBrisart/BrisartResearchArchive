"""
tests/test_service_registry.py

Purpose
-------
Unit tests for `brisartos/services/service_registry.py`
(`ServiceRecord`, `ServiceRegistry`). The registry is the single place
`BrisartRuntime` and `ModuleAPI.get_service()` both go through to look up
a built-in service by name, so these tests confirm registration,
lookup-by-name, "not found" handling, and the `describe()`/`status_all()`
metadata contract that `BrisartRuntime.print_services()` and
`describe_service()` render directly to the shell.

Communication relationships
----------------------------
- `register_builtin_services()` wires up exactly the four services shipped
  today (`ArchiveService`, `FilesystemService`, `SettingsService`,
  `UpdateService`) under the fixed names `"archive"`, `"filesystem"`,
  `"settings"`, `"update"`. `tests/test_runtime.py` exercises this method
  indirectly through `BrisartRuntime.boot()`.
- `get_service_object()` is the accessor `ModuleAPI.get_service()` calls
  (see `tests/test_module_api.py`) to hand a module the live service
  instance once its `service:<name>` permission has been verified. This
  file tests it directly, against the registry alone, with no permission
  layer involved.

Settings / parameters
----------------------
- `ServiceRegistry(module_data_root=None)`: `module_data_root` is only
  forwarded to `FilesystemService` inside `register_builtin_services()`;
  registering services manually via `register()` does not require it.
  Because `FilesystemService.__init__` creates its data directory
  relative to `Path.cwd()` whenever `module_data_root` is falsy (see
  `tests/test_filesystem_service.py`), the two
  `ServiceRegistryBuiltinServicesTests` cases below run inside
  `_support.IsolatedCwd` even though `ServiceRegistry` itself has no
  filesystem side effects of its own.
- `register(name, display_name, service)`: last write for a given `name`
  wins (backed by a plain `dict`), so re-registering under an existing
  name silently replaces the previous `ServiceRecord`.

Edge-case behavior
-------------------
- `get()`, `describe()`, and `get_service_object()` must all return `None`
  for an unregistered name rather than raising `KeyError`, since
  `BrisartRuntime.describe_service()` relies on a `None` return to print
  "service not found" instead of crashing the shell.
- `names()` must return service names in sorted order, matching
  `BrisartRuntime.print_modules()`'s use of `sorted(...)` for the parallel
  module listing.
- A `ServiceRecord` wrapping an object with no `status()` method must fall
  back to the literal string `"Status unavailable"` rather than raising
  `AttributeError`.
"""
import unittest

from _support import IsolatedCwd, add_brisartos_services_to_syspath

add_brisartos_services_to_syspath()

from service_registry import ServiceRecord, ServiceRegistry  # noqa: E402


class FakeService:
    def __init__(self, version="1.0.0", status_text="Fake Service Online"):
        self.version = version
        self._status_text = status_text

    def status(self):
        return self._status_text


class NoStatusService:
    """A service deliberately missing a status() method."""
    version = "0.0.1"


class ServiceRecordTests(unittest.TestCase):
    def test_status_delegates_to_service(self):
        record = ServiceRecord("fake", "Fake Service", FakeService())
        self.assertEqual(record.status(), "Fake Service Online")

    def test_status_falls_back_when_service_has_no_status_method(self):
        record = ServiceRecord("no_status", "No Status Service", NoStatusService())
        self.assertEqual(record.status(), "Status unavailable")

    def test_describe_includes_all_expected_fields(self):
        record = ServiceRecord("fake", "Fake Service", FakeService(version="2.0.0"))
        description = record.describe()
        self.assertEqual(description["name"], "fake")
        self.assertEqual(description["display_name"], "Fake Service")
        self.assertEqual(description["version"], "2.0.0")
        self.assertEqual(description["status"], "Fake Service Online")
        self.assertEqual(description["class"], "FakeService")

    def test_describe_version_defaults_to_unknown_if_missing(self):
        class VersionlessService:
            def status(self):
                return "ok"

        record = ServiceRecord("versionless", "Versionless", VersionlessService())
        self.assertEqual(record.describe()["version"], "unknown")


class ServiceRegistryRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.registry = ServiceRegistry()

    def test_register_and_get(self):
        service = FakeService()
        self.registry.register("fake", "Fake Service", service)
        record = self.registry.get("fake")
        self.assertIsNotNone(record)
        self.assertIs(record.service, service)

    def test_get_unregistered_name_returns_none(self):
        self.assertIsNone(self.registry.get("does_not_exist"))

    def test_has_service_true_and_false(self):
        self.registry.register("fake", "Fake Service", FakeService())
        self.assertTrue(self.registry.has_service("fake"))
        self.assertFalse(self.registry.has_service("nope"))

    def test_registering_same_name_twice_replaces_the_record(self):
        first = FakeService(version="1.0.0")
        second = FakeService(version="2.0.0")
        self.registry.register("fake", "Fake Service", first)
        self.registry.register("fake", "Fake Service", second)
        self.assertIs(self.registry.get_service_object("fake"), second)

    def test_get_service_object_returns_none_for_unregistered_name(self):
        self.assertIsNone(self.registry.get_service_object("nope"))

    def test_get_service_object_returns_raw_service_not_the_record(self):
        service = FakeService()
        self.registry.register("fake", "Fake Service", service)
        self.assertIs(self.registry.get_service_object("fake"), service)

    def test_names_returns_sorted_list(self):
        self.registry.register("zeta", "Zeta", FakeService())
        self.registry.register("alpha", "Alpha", FakeService())
        self.registry.register("mid", "Mid", FakeService())
        self.assertEqual(self.registry.names(), ["alpha", "mid", "zeta"])

    def test_describe_unregistered_name_returns_none(self):
        self.assertIsNone(self.registry.describe("nope"))

    def test_status_all_returns_describe_for_every_service_sorted(self):
        self.registry.register("zeta", "Zeta", FakeService())
        self.registry.register("alpha", "Alpha", FakeService())
        statuses = self.registry.status_all()
        names_in_order = [entry["name"] for entry in statuses]
        self.assertEqual(names_in_order, ["alpha", "zeta"])

    def test_status_all_empty_registry_returns_empty_list(self):
        self.assertEqual(self.registry.status_all(), [])


class ServiceRegistryBuiltinServicesTests(unittest.TestCase):
    def test_register_builtin_services_registers_all_four(self):
        with IsolatedCwd():
            registry = ServiceRegistry(module_data_root=None)
            registry.register_builtin_services()
            self.assertEqual(
                registry.names(),
                ["archive", "filesystem", "settings", "update"],
            )

    def test_builtin_services_report_online_status(self):
        with IsolatedCwd():
            registry = ServiceRegistry(module_data_root=None)
            registry.register_builtin_services()
            for name in registry.names():
                status = registry.describe(name)["status"]
                self.assertIn("Online", status)


if __name__ == "__main__":
    unittest.main()
