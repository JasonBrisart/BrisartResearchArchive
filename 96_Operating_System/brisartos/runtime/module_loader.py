"""
BrisartOS Module Loader
Pure Python.
No dependencies.
"""
from pathlib import Path
import importlib.util
from module_api import ModuleAPI
class LoadedModule:
    def __init__(self, path, module_object, api, service_registry=None):
        self.path = path
        self.module_object = module_object
        self.api = api
        self.service_registry = service_registry
        self.name = module_object.MODULE_NAME
        self.display_name = module_object.MODULE_DISPLAY_NAME
        self.version = module_object.MODULE_VERSION
        self.author = module_object.MODULE_AUTHOR
        self.description = module_object.MODULE_DESCRIPTION
        self.abi = module_object.MODULE_ABI
        self.permissions = module_object.MODULE_PERMISSIONS
    def run(self):
        module_api = ModuleAPI(
            module_name=self.name,
            permissions=self.permissions,
            system_api=self.api,
            service_registry=self.service_registry
        )
        self.api.log(
            self.name,
            "module started"
        )
        self.module_object.run(module_api)
        self.api.log(
            self.name,
            "module finished"
        )
class ModuleLoader:
    SUPPORTED_ABI = "brisartos.module.v1"
    def __init__(self, modules_path, api, service_registry=None):
        self.modules_path = Path(modules_path)
        self.api = api
        self.service_registry = service_registry
        self.modules = {}
    def get(self, name):
        return self.modules.get(name)
    def discover(self):
        self.modules = {}
        if not self.modules_path.exists():
            self.modules_path.mkdir(
                parents=True,
                exist_ok=True
            )
        for folder in self.modules_path.iterdir():
            if not folder.is_dir():
                continue
            module_file = folder / "module.py"
            if not module_file.exists():
                continue
            try:
                loaded = self._load_module(
                    folder,
                    module_file
                )
            except Exception as error:
                print(
                    f"failed to load "
                    f"{folder.name}: {error}"
                )
                continue
            if loaded.abi != self.SUPPORTED_ABI:
                print(
                    f"failed to load "
                    f"{folder.name}: unsupported ABI "
                    f"{loaded.abi}"
                )
                continue
            self.modules[loaded.name] = loaded
    def _load_module(
        self,
        folder,
        module_file
    ):
        module_name = (
            "brisartos_module_"
            + folder.name
        )
        spec = (
            importlib.util
            .spec_from_file_location(
                module_name,
                module_file
            )
        )
        if spec is None:
            raise ImportError(
                f"could not create module spec for "
                f"{module_file}"
            )
        if spec.loader is None:
            raise ImportError(
                f"could not create module loader for "
                f"{module_file}"
            )
        module_object = (
            importlib.util
            .module_from_spec(spec)
        )
        spec.loader.exec_module(
            module_object
        )
        return LoadedModule(
            folder,
            module_object,
            self.api,
            self.service_registry
        )
