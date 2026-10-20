r"""
File: brisartos/extensions/registry.py

Purpose
-------
Register callable module entries, discover module files and run entries with a
ModuleAPI while recording load failures and execution logs.

Public interface:
- class ModuleRegistry -- The table of modules and the reasons any failed to
  load.
- ModuleRegistry(kernel) -- Bind the kernel that modules will receive.
- ModuleRegistry.register(name, entry, permissions=(), description='',
  author='', version=__version__, origin='code', display_name=None) -- Add a
  module from code after validating its name, entry point and permissions.
- ModuleRegistry.discover(folder) -- Replace the folder-discovered modules from
  a folder and return {folder: reason} for each that failed.
- ModuleRegistry.run(name) -- Run a module, logging module started and then
  finished or failed, and return its result.
- ModuleRegistry.describe(name) -- Return a module's record without its entry
  function.
- ModuleRegistry.names() -- Return the sorted module names.

Design notes:

Discovery retains records whose origin is code and replaces the other records,
executing each file before checking required declarations and ABI
compatibility. Exception failures are collected per folder. run logs before
invocation and after success; BaseException from the entry is logged and
re-raised. Logging failures themselves are not recovered here.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.common.names (brisartos/common/names.py)
- brisartos.extensions.api (brisartos/extensions/api.py)
- brisartos.host.loader (brisartos/host/loader.py)
- version (version.py)
Standard library: none.
Imported by:
- brisartos/kernel/kernel.py
Covered by tests: brisartos/extensions/tests/test_registry.py.

Settings / parameters
---------------------
- REQUIRED_NAMES -- The eight names a module file must define: MODULE_NAME,
  MODULE_DISPLAY_NAME, MODULE_VERSION, MODULE_AUTHOR, MODULE_DESCRIPTION,
  MODULE_ABI, MODULE_PERMISSIONS and run.

Edge cases
----------
A module that fails to import, lacks a required name, declares another ABI, has
an unsafe or duplicate name or an invalid permission list is skipped and
recorded in failures. Running or describing an unknown module raises KeyError.

- ModuleRegistry.register() raises ValueError: "module already registered:
  {...}"
- ModuleRegistry.register() raises TypeError: "module entry must be callable"
- ModuleRegistry.discover() raises ValueError: "missing {...}"
- ModuleRegistry.discover() raises ValueError: "unsupported ABI {...}"
- ModuleRegistry.run() re-raises the active exception
- ModuleRegistry.describe() raises KeyError: "unknown module: {...}"
- ModuleRegistry.discover() catches Exception -- Any failure while loading or
  registering one module becomes a recorded reason instead of stopping
  discovery of the rest.
- ModuleRegistry.run() catches BaseException -- Logs the failure, including
  SystemExit and KeyboardInterrupt, then re-raises unchanged.

Known limitations
-----------------
- Discovery executes module code before any check, and re-discovering executes
  every module file again.
- When two folders declare the same MODULE_NAME the alphabetically first wins
  and the other is reported as a failure.
- A module's module-level variables persist between runs for the life of the
  process, and reload resets them.

Examples
--------
Run from the repository root.

::

    from brisartos.kernel.kernel import Kernel

    kernel = Kernel()
    kernel.start()
    kernel.modules.register('greeter', lambda api: api.write_text('hi.txt', 'hi'), ('storage',))
    assert kernel.modules.run('greeter') == '/modules/greeter/hi.txt'
    assert 'module finished' in kernel.storage.read('/logs/greeter.log')
"""

from version import __version__
from ..common.names import require_name
from ..host import loader
from .api import MODULE_ABI, ModuleAPI, check_permissions

REQUIRED_NAMES = ('MODULE_NAME', 'MODULE_DISPLAY_NAME', 'MODULE_VERSION', 'MODULE_AUTHOR',
                  'MODULE_DESCRIPTION', 'MODULE_ABI', 'MODULE_PERMISSIONS', 'run')


class ModuleRegistry:
    def __init__(self, kernel):
        self._kernel = kernel
        self._modules = {}
        self.failures = {}

    def register(self, name, entry, permissions=(), description='', author='',
                 version=__version__, origin='code', display_name=None):
        require_name(name, 'module name')
        if name in self._modules:
            raise ValueError('module already registered: ' + name)
        if not callable(entry):
            raise TypeError('module entry must be callable')
        permissions = check_permissions(permissions)
        self._modules[name] = {'name': name, 'display_name': display_name or name, 'entry': entry,
                               'permissions': permissions,
                               'description': description, 'author': author,
                               'version': version, 'origin': origin}

    def discover(self, folder):
        self._modules = {name: info for name, info in self._modules.items()
                         if info['origin'] == 'code'}
        self.failures = {}
        for path in loader.module_files(folder):
            label = path.parent.name
            try:
                module = loader.load_module(path)
                missing = [item for item in REQUIRED_NAMES if not hasattr(module, item)]
                if missing:
                    raise ValueError('missing ' + ', '.join(missing))
                if module.MODULE_ABI != MODULE_ABI:
                    raise ValueError('unsupported ABI ' + str(module.MODULE_ABI))
                self.register(module.MODULE_NAME, module.run, module.MODULE_PERMISSIONS,
                              module.MODULE_DESCRIPTION, module.MODULE_AUTHOR,
                              module.MODULE_VERSION, str(path), module.MODULE_DISPLAY_NAME)
            except Exception as error:
                self.failures[label] = type(error).__name__ + ': ' + str(error)
        return dict(self.failures)

    def run(self, name):
        info = self.describe(name)
        api = ModuleAPI(self._kernel, name, info['permissions'])
        self._kernel.log(name, 'module started')
        try:
            result = self._modules[name]['entry'](api)
        except BaseException as error:
            self._kernel.log(name, 'module failed: ' + type(error).__name__ + ': ' + str(error))
            raise
        self._kernel.log(name, 'module finished')
        return result

    def describe(self, name):
        if name not in self._modules:
            raise KeyError('unknown module: ' + str(name))
        return {key: value for key, value in self._modules[name].items() if key != 'entry'}

    def names(self):
        return sorted(self._modules)
