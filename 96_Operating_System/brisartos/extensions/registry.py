r"""
File: brisartos/extensions/registry.py

Purpose
-------
Register compatible modules, validate manifests before execution, invoke
permission-gated entries and collect shutdown failures.

Public interface:
- class ModuleRegistry -- Registered module metadata, entries and optional
  cleanup hooks.
- ModuleRegistry(context) -- Bind the runtime module context.
- ModuleRegistry.register(name, entry, permissions=(), description='',
  author='', version=__version__, origin='code', display_name=None, api=None,
  shutdown=None) -- Validate and register an entry, API requirement and
  optional shutdown hook.
- ModuleRegistry.discover(folder) -- Replace discovered entries; validate inert
  manifests before loading new-format modules.
- ModuleRegistry.run(name) -- Invoke an entry while accepting work and record
  structured outcomes.
- ModuleRegistry.describe(name) -- Return copied metadata without the entry
  callable.
- ModuleRegistry.names() -- Return sorted module names.
- ModuleRegistry.stop_all() -- Invoke cleanup hooks in reverse registration
  order and collect failures.

Design notes:

Manifest metadata is authoritative for new modules; legacy declarations remain
a fallback. host/loader.py reads the manifest text and manifest.py parses it,
so manifest rules live in this layer. Compatibility checks precede import for
manifest entries. Shutdown hooks take no arguments and must release their own
resources.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.common.names (brisartos/common/names.py)
- brisartos.extensions.api (brisartos/extensions/api.py)
- brisartos.extensions.contracts (brisartos/extensions/contracts.py)
- brisartos.extensions.manifest (brisartos/extensions/manifest.py)
- brisartos.host.loader (brisartos/host/loader.py)
- version (version.py)
Standard library: none.
Imported by:
- brisartos/kernel/composition.py
Covered by tests: brisartos/extensions/tests/test_registry.py.

Settings / parameters
---------------------
- REQUIRED_NAMES -- The eight declarations a manifest-free legacy module must
  define.

Edge cases
----------
Invalid inputs are rejected before the documented operation; backend and
callback failures propagate unless explicitly collected.

- ModuleRegistry.register() raises ValueError: "module already registered:
  {...}"
- ModuleRegistry.register() raises TypeError: "module entry must be callable"
- ModuleRegistry.register() raises TypeError: "module shutdown must be
  callable"
- ModuleRegistry.discover() raises ValueError: "module already registered:
  {...}"
- ModuleRegistry.discover() raises ValueError: "missing {...}"
- ModuleRegistry.discover() raises ValueError: "unsupported ABI {...}"
- ModuleRegistry.run() raises RuntimeError: "runtime is not accepting module
  calls"
- ModuleRegistry.run() re-raises the active exception
- ModuleRegistry.describe() raises KeyError: "unknown module: {...}"
- ModuleRegistry.discover() catches Exception -- Collect the failure as
  documented and continue cleanup or report it to the caller.
- ModuleRegistry.run() catches BaseException -- Collect the failure as
  documented and continue cleanup or report it to the caller.
- ModuleRegistry.stop_all() catches BaseException -- Collect the failure as
  documented and continue cleanup or report it to the caller.

Known limitations
-----------------
- Legacy declaration-only modules execute before validation.
- Trusted modules can bypass API permissions; manifests and facades are not a
  sandbox.
- Reload replaces discovered objects without transactional rollback or
  guaranteed old-resource cleanup.

Examples
--------
Run from the repository root.

::

    from brisartos.kernel.kernel import Kernel
    k = Kernel()
    k.start()
    k.modules.register('demo', lambda api: 'ok')
    assert k.modules.run('demo') == 'ok'
    k.stop()
"""
from version import __version__
from ..common.names import require_name
from ..host import loader
from .api import MODULE_ABI, ModuleAPI, check_permissions
from .contracts import check_compatibility
from .manifest import parse_manifest

REQUIRED_NAMES = ('MODULE_NAME', 'MODULE_DISPLAY_NAME', 'MODULE_VERSION', 'MODULE_AUTHOR',
                  'MODULE_DESCRIPTION', 'MODULE_ABI', 'MODULE_PERMISSIONS', 'run')


class ModuleRegistry:
    def __init__(self, context):
        self.context = context
        self._modules = {}
        self.failures = {}
        self._shutdown = {}

    def register(self, name, entry, permissions=(), description='', author='',
                 version=__version__, origin='code', display_name=None, api=None, shutdown=None):
        require_name(name, 'module name')
        if name in self._modules:
            raise ValueError('module already registered: ' + name)
        if not callable(entry):
            raise TypeError('module entry must be callable')
        permissions = check_permissions(permissions)
        api = check_compatibility(('brisartos.module', 1, 0) if api is None else api)
        if shutdown is not None and not callable(shutdown):
            raise TypeError('module shutdown must be callable')
        self._shutdown[name] = shutdown
        self._modules[name] = {'name': name, 'display_name': display_name or name, 'entry': entry,
                               'permissions': permissions,
                               'description': description, 'author': author,
                               'version': version, 'origin': origin, 'api': api}

    def discover(self, folder):
        self._modules = {name: info for name, info in self._modules.items()
                         if info['origin'] == 'code'}
        self.failures = {}
        self._shutdown = {name: hook for name, hook in self._shutdown.items() if name in self._modules}
        for path in loader.module_files(folder):
            label = path.parent.name
            try:
                text = loader.read_manifest_text(path)
                if text is not None:
                    manifest = parse_manifest(text)
                    require_name(manifest['name'], 'module name')
                    check_permissions(manifest['permissions'])
                    api = check_compatibility((manifest['api'], manifest['api_major'], manifest['api_minor']))
                    if manifest['name'] in self._modules:
                        raise ValueError('module already registered: ' + manifest['name'])
                    module = loader.load_module(path)
                    self.register(manifest['name'], getattr(module, 'run', None), manifest['permissions'],
                                  manifest['description'], manifest['author'],
                                  __version__ if manifest['version'] == 'runtime' else manifest['version'],
                                  str(path), manifest['display_name'], api, getattr(module, 'stop', None))
                    continue
                module = loader.load_module(path)
                missing = [item for item in REQUIRED_NAMES if not hasattr(module, item)]
                if missing:
                    raise ValueError('missing ' + ', '.join(missing))
                if module.MODULE_ABI != MODULE_ABI:
                    raise ValueError('unsupported ABI ' + str(module.MODULE_ABI))
                self.register(module.MODULE_NAME, module.run, module.MODULE_PERMISSIONS,
                              module.MODULE_DESCRIPTION, module.MODULE_AUTHOR,
                              module.MODULE_VERSION, str(path), module.MODULE_DISPLAY_NAME,
                              getattr(module, 'MODULE_API', None), getattr(module, 'stop', None))
            except Exception as error:
                self.failures[label] = type(error).__name__ + ': ' + str(error)
        return dict(self.failures)

    def run(self, name):
        if not self.context.accepting:
            raise RuntimeError('runtime is not accepting module calls')
        info = self.describe(name)
        api = ModuleAPI(self.context, name, info['permissions'])
        self.context.events.record(name, 'module started', kind='module.started', details={'module': name})
        try:
            result = self._modules[name]['entry'](api)
        except BaseException as error:
            self.context.events.record(name, 'module failed: ' + type(error).__name__ + ': ' + str(error), kind='module.failed', details={'module': name})
            raise
        self.context.events.record(name, 'module finished', kind='module.finished', details={'module': name})
        return result

    def describe(self, name):
        if name not in self._modules:
            raise KeyError('unknown module: ' + str(name))
        return {key: value for key, value in self._modules[name].items() if key != 'entry'}

    def names(self):
        return sorted(self._modules)
    def stop_all(self):
        failures = []
        for name in reversed(list(self._modules)):
            hook = self._shutdown.get(name)
            if hook is not None:
                try:
                    hook()
                except BaseException as error:
                    failures.append({'module': name, 'error': type(error).__name__ + ': ' + str(error)})
        self._shutdown = {}
        return failures
