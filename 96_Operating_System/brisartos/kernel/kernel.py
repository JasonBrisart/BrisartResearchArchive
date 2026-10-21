r"""
File: brisartos/kernel/kernel.py

Purpose
-------
Coordinate explicit startup, work acceptance and best-effort reverse shutdown
over an injected component bundle.

Public interface:
- class Kernel -- The lifecycle coordinator for a composed runtime.
- Kernel(data_root=None, modules_path=None, max_steps=10000, event_limit=1000,
  components=None) -- Build or accept explicit components and retain runtime
  options.
- Kernel.start() -- Validate schema, start services, record startup and
  discover modules.
- Kernel.reload_modules() -- Discover modules only while running and record
  structured outcomes.
- Kernel.stop() -- Block new work, run all cleanup phases and return failure
  records.
- Kernel.run_file(path) -- Execute stored restricted-language source only while
  running.
- Kernel.describe() -- Return the existing seven-field runtime description.

Design notes:

Construction delegates assembly to composition.py. Startup validates
stored-data format before services load. Any startup failure enters cleanup.
Shutdown blocks module API work, cancels tasks, runs module hooks, stops
services and records a final event.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.extensions.api (brisartos/extensions/api.py)
- brisartos.kernel.composition (brisartos/kernel/composition.py)
- brisartos.storage.schema (brisartos/storage/schema.py)
Standard library: none.
Imported by:
- brisartos/shell/console.py
Covered by tests: brisartos/extensions/tests/test_api.py,
brisartos/extensions/tests/test_registry.py,
brisartos/kernel/tests/test_architecture.py,
brisartos/kernel/tests/test_kernel.py, brisartos/shell/tests/test_console.py,
brisartos/shell/tests/test_shell.py.

Settings / parameters
---------------------
Constructor arguments select the supplied components and policies; no
module-level configuration is defined.

Edge cases
----------
Invalid inputs are rejected before the documented operation; backend and
callback failures propagate unless explicitly collected.

- Kernel.start() raises RuntimeError: "kernel can only start once"
- Kernel.start() re-raises the active exception
- Kernel.reload_modules() raises RuntimeError: "kernel is not running"
- Kernel.stop() raises RuntimeError: "kernel is not running"
- Kernel.run_file() raises RuntimeError: "kernel is not running"
- Kernel.start() catches BaseException -- Collect the failure as documented and
  continue cleanup or report it to the caller.
- Kernel._shutdown() catches BaseException -- Collect the failure as documented
  and continue cleanup or report it to the caller.

Known limitations
-----------------
- A stopped kernel cannot restart; construct a new instance.
- Cleanup is best effort and cannot interrupt a non-returning hook; errors are
  retained in shutdown_errors.
- This is a single host-Python process, not an independent bootable operating
  system.

Examples
--------
Run from the repository root.

::

    from brisartos.kernel.kernel import Kernel
    k = Kernel()
    k.start()
    k.storage.write('/p.py', 'print(42)')
    assert k.run_file('/p.py')['output'] == ['42']
    assert k.stop() == []
    assert k.state == 'stopped'
"""
from ..extensions.api import MODULE_ABI
from ..storage.schema import initialize
from .composition import build_runtime

class Kernel:
    def __init__(self, data_root=None, modules_path=None, max_steps=10000, event_limit=1000, components=None):
        components = build_runtime(data_root, modules_path, max_steps, event_limit) if components is None else components
        self.components = components
        self.storage, self.scheduler, self.devices = components.storage, components.scheduler, components.devices
        self.console, self.events, self.services = components.console, components.events, components.services
        self.modules, self.language, self.platform = components.modules, components.language, components.platform
        self.modules_path, self.state = modules_path, 'created'
        self.shutdown_errors = []
    def start(self):
        if self.state != 'created':
            raise RuntimeError('kernel can only start once')
        self.state = 'starting'
        try:
            initialize(self.storage)
            self.services.start_all()
            self.events.record('kernel', 'started on host Python; no firmware boot occurred', kind='kernel.started')
            self.state = 'running'
            self.modules.context.open()
            if self.modules_path is not None:
                self.reload_modules()
        except BaseException:
            self._shutdown()
            raise
    def reload_modules(self):
        if self.state != 'running':
            raise RuntimeError('kernel is not running')
        if self.modules_path is None:
            return {}
        failures = self.modules.discover(self.modules_path)
        for name in self.modules.names():
            self.events.record('kernel', 'module ' + name + ' loaded', kind='module.loaded', details={'module': name})
        for label, reason in sorted(failures.items()):
            self.events.record('kernel', 'module ' + label + ' not loaded: ' + reason, kind='module.rejected', details={'module': label, 'reason': reason})
        return failures
    def _shutdown(self):
        self.state = 'stopping'
        self.modules.context.close()
        self.shutdown_errors = []
        for name, cleanup in (('tasks', self.scheduler.cancel_all), ('modules', self.modules.stop_all), ('services', self.services.stop_all)):
            try:
                result = cleanup()
                if isinstance(result, list):
                    self.shutdown_errors.extend(result)
            except BaseException as error:
                self.shutdown_errors.append({'component': name, 'error': type(error).__name__ + ': ' + str(error)})
        self.shutdown_errors.extend(self.scheduler.cleanup_errors)
        self.shutdown_errors.extend(self.services.lifecycle_errors)
        try:
            self.events.record('kernel', 'stopped', kind='kernel.stopped', details={'cleanup_errors': len(self.shutdown_errors)})
        except BaseException as error:
            self.shutdown_errors.append({'component': 'events', 'error': type(error).__name__ + ': ' + str(error)})
        self.state = 'stopped'
    def stop(self):
        if self.state != 'running':
            raise RuntimeError('kernel is not running')
        self._shutdown()
        return list(self.shutdown_errors)
    def run_file(self, path):
        if self.state != 'running':
            raise RuntimeError('kernel is not running')
        return self.language.run(self.storage.read(path))
    def describe(self):
        return {'state': self.state, 'platform': self.platform.describe(),
                'module_abi': MODULE_ABI, 'storage': self.storage.describe(),
                'services': self.services.names(), 'modules': self.modules.names(), 'events': self.events.total}
