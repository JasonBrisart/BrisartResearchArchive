"""
BrisartOS Runtime
Pure Python.
No dependencies.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services"))
from version import NAME as BRISART_NAME, VERSION as BRISART_VERSION
from brisart_platform import PlatformInfo
from system_api import SystemAPI
from module_loader import ModuleLoader
from service_registry import ServiceRegistry
class BrisartRuntime:
    NAME = BRISART_NAME
    VERSION = BRISART_VERSION
    PROFILE = "Modular Research Operating Environment"
    def __init__(self):
        self.platform = PlatformInfo()
        self.api = SystemAPI(self.platform)
        self.services = ServiceRegistry(
            module_data_root=self.api.module_data_root
        )
        self.loader = ModuleLoader(
            modules_path="modules",
            api=self.api,
            service_registry=self.services,
        )
    def boot(self):
        print()
        print("===================================")
        print(" BrisartOS Runtime Boot")
        print("===================================")
        print(f"Version : {self.VERSION}")
        print(f"Profile : {self.PROFILE}")
        print()
        self.services.register_builtin_services()
        self.loader.discover()
    def version_text(self):
        return (
            f"{self.NAME} {self.VERSION}\n"
            "Pure Python. No Dependencies. Modular."
        )
    def print_system_info(self):
        print()
        info = self.platform.describe()
        for key in sorted(info):
            print(f"{key}: {info[key]}")
        print()
    def print_modules(self):
        print()
        if not self.loader.modules:
            print("No modules found.")
            print()
            return
        for name in sorted(self.loader.modules):
            module = self.loader.modules[name]
            print(f"{name} - {module.display_name}")
        print()
    def describe_module(self, name):
        module = self.loader.get(name)
        if module is None:
            print("module not found")
            return
        print()
        print("Name:", module.name)
        print("Display Name:", module.display_name)
        print("Version:", module.version)
        print("Author:", module.author)
        print("ABI:", module.abi)
        print("Permissions:", ", ".join(module.permissions))
        print()
        print(module.description)
        print()
    def run_module(self, name):
        module = self.loader.get(name)
        if module is None:
            print("module not found")
            return
        module.run()
    def reload_modules(self):
        self.loader.discover()
        print("modules reloaded")
    def print_services(self):
        print()
        services = self.services.status_all()
        if not services:
            print("No services registered.")
            print()
            return
        for service in services:
            print(
                f"{service['name']} - "
                f"{service['display_name']} - "
                f"{service['status']}"
            )
        print()
    def describe_service(self, name):
        service = self.services.describe(name)
        if service is None:
            print("service not found")
            return
        print()
        print("Name:", service["name"])
        print("Display Name:", service["display_name"])
        print("Version:", service["version"])
        print("Class:", service["class"])
        print("Status:", service["status"])
        print()