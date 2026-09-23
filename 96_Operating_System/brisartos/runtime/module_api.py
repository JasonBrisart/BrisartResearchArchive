"""
BrisartOS Module API Wrapper
Pure Python.
No dependencies.
This file provides a permission-aware API surface for modules.
Modules should receive this wrapper instead of the unrestricted
core SystemAPI object.
"""
class PermissionError(Exception):
    pass
class ServiceUnavailableError(Exception):
    pass
class ModuleAPI:
    def __init__(self, module_name, permissions, system_api, service_registry=None):
        self.module_name = module_name
        self.permissions = set(permissions)
        self.system_api = system_api
        self.service_registry = service_registry
    def require(self, permission):
        if permission not in self.permissions:
            raise PermissionError(
                f"module '{self.module_name}' does not have "
                f"permission '{permission}'"
            )
    def now_utc(self):
        return self.system_api.now_utc()
    def new_object_id(self):
        self.require("object_id")
        return self.system_api.new_object_id()
    def log(self, source, message):
        self.require("log")
        return self.system_api.log(source, message)
    def module_data_path(self, module_name):
        self.require("module_data")
        return self.system_api.module_data_path(module_name)
    def write_module_text(self, module_name, filename, text):
        self.require("module_data")
        return self.system_api.write_module_text(
            module_name,
            filename,
            text,
        )
    def read_module_text(self, module_name, filename):
        self.require("module_data")
        return self.system_api.read_module_text(
            module_name,
            filename,
        )
    def get_platform_info(self):
        self.require("platform_info")
        return self.system_api.get_platform_info()
    def get_service(self, name):
        """
        Return the live service instance registered under `name`
        (e.g. "archive", "filesystem", "settings", "update").
        Requires the module to declare permission "service:<name>"
        in MODULE_PERMISSIONS.
        """
        self.require(f"service:{name}")
        if self.service_registry is None:
            raise ServiceUnavailableError(
                "no service registry attached to this runtime"
            )
        service = self.service_registry.get_service_object(name)
        if service is None:
            raise ServiceUnavailableError(
                f"service '{name}' is not registered"
            )
        return service
    def available_services(self):
        """
        Return the list of registered service names, regardless of
        whether this module currently holds permission to use any
        of them. Useful for module diagnostics/help output.
        """
        if self.service_registry is None:
            return []
        return self.service_registry.names()
