"""
BrisartOS Service Registry
Pure Python.
No dependencies.
The service registry provides a stable runtime-owned place
for BrisartOS services to be registered, listed, inspected,
and queried without requiring shell commands or modules to
know the internal service implementation details.
"""
from archive_service import ArchiveService
from filesystem_service import FilesystemService
from settings_service import SettingsService
from update_service import UpdateService
class ServiceRecord:
    def __init__(self, name, display_name, service):
        self.name = name
        self.display_name = display_name
        self.service = service
    def status(self):
        if hasattr(self.service, "status"):
            return self.service.status()
        return "Status unavailable"
    def describe(self):
        return {
            "name": self.name,
            "display_name": self.display_name,
            "version": getattr(self.service, "version", "unknown"),
            "status": self.status(),
            "class": self.service.__class__.__name__,
        }
class ServiceRegistry:
    def __init__(self, module_data_root=None):
        self.services = {}
        self.module_data_root = module_data_root
    def register(self, name, display_name, service):
        self.services[name] = ServiceRecord(
            name=name,
            display_name=display_name,
            service=service,
        )
    def register_builtin_services(self):
        self.register(
            "archive",
            "Archive Service",
            ArchiveService(),
        )
        self.register(
            "filesystem",
            "Filesystem Service",
            FilesystemService(self.module_data_root),
        )
        self.register(
            "settings",
            "Settings Service",
            SettingsService(),
        )
        self.register(
            "update",
            "Update Service",
            UpdateService(),
        )
    def get(self, name):
        return self.services.get(name)
    def has_service(self, name):
        return name in self.services
    def get_service_object(self, name):
        """
        Return the raw service instance registered under `name`,
        or None if no service is registered under that name.
        This is the accessor used by ModuleAPI.get_service() so
        that modules can call real service methods directly,
        instead of only reading status/describe metadata through
        the ServiceRecord wrapper.
        """
        record = self.get(name)
        if record is None:
            return None
        return record.service
    def names(self):
        return sorted(self.services)
    def describe(self, name):
        record = self.get(name)
        if record is None:
            return None
        return record.describe()
    def status_all(self):
        results = []
        for name in self.names():
            record = self.services[name]
            results.append(record.describe())
        return results