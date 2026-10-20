r"""
File: brisartos/kernel/kernel.py

Purpose
-------
Compose the BrisartOS runtime and coordinate its one-way lifecycle, module
discovery, event recording and stored-program execution.

Public interface:
- class Kernel -- The composition root: storage, scheduler, devices, services,
  modules, language and platform facts.
- Kernel(data_root=None, modules_path=None, max_steps=10000, event_limit=1000)
  -- Build every component; data_root selects disk storage, modules_path a
  folder of modules to discover.
- Kernel.start() -- Register the settings, archive and updates services, log
  the start and discover modules.
- Kernel.reload_modules() -- Rediscover modules, log each failure and return
  the failures mapping.
- Kernel.stop() -- Cancel every waiting task and log the stop.
- Kernel.run_file(path) -- Run a stored file with the restricted language and
  return its result.
- Kernel.describe() -- Return the state, platform facts, ABI, storage,
  services, modules and total event count.

Design notes:

Construction selects a storage backend and builds the components, then hands
the module system a ModuleContext holding only storage, services, the event log
and platform facts, so module code never receives the kernel itself. start
registers three services before recording the start and discovering modules;
stop cancels waiting tasks before recording the stop and changing state. Every
kernel event goes through the same EventLog that modules write to.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.events.events (brisartos/events/events.py)
- brisartos.extensions.api (brisartos/extensions/api.py)
- brisartos.extensions.registry (brisartos/extensions/registry.py)
- brisartos.host.disk (brisartos/host/disk.py)
- brisartos.host.system (brisartos/host/system.py)
- brisartos.kernel.devices (brisartos/kernel/devices.py)
- brisartos.kernel.platform (brisartos/kernel/platform.py)
- brisartos.kernel.scheduler (brisartos/kernel/scheduler.py)
- brisartos.language.interpreter (brisartos/language/interpreter.py)
- brisartos.services.archive (brisartos/services/archive.py)
- brisartos.services.registry (brisartos/services/registry.py)
- brisartos.services.settings (brisartos/services/settings.py)
- brisartos.services.updates (brisartos/services/updates.py)
- brisartos.storage.storage (brisartos/storage/storage.py)
Standard library: none.
Imported by:
- brisartos/shell/console.py
Covered by tests: brisartos/extensions/tests/test_api.py,
brisartos/extensions/tests/test_registry.py,
brisartos/kernel/tests/test_kernel.py, brisartos/shell/tests/test_console.py,
brisartos/shell/tests/test_shell.py.

Settings / parameters
---------------------
Kernel(data_root=None, modules_path=None, max_steps=10000, event_limit=1000).
With data_root=None files live in memory; with a folder they live on disk
there. With modules_path=None no modules are discovered.

Edge cases
----------
A module that fails to load is recorded as "module NAME not loaded: REASON" and
never stops start. An invalid event_limit is refused by the event log during
construction. run_file lets storage and language errors pass through to the
caller.

- Kernel.start() raises RuntimeError: "kernel can only start once"
- Kernel.stop() raises RuntimeError: "kernel is not running"

Known limitations
-----------------
- A stopped kernel cannot restart; build a new one.
- Everything runs in one host Python process with no isolation between the
  kernel, the shell and modules.
- Settings, snapshots and update candidates live in memory only, so they are
  not restored when a new kernel opens the same data folder.

Examples
--------
Run from the repository root.

::

    from brisartos.kernel.kernel import Kernel

    kernel = Kernel()
    kernel.start()
    kernel.storage.write('/p.py', 'print(6 * 7)')
    assert kernel.run_file('/p.py')['output'] == ['42']
    kernel.stop()
    assert kernel.state == 'stopped'
"""

from ..host import disk, system
from ..language.interpreter import Interpreter
from ..events.events import EventLog
from ..extensions.api import MODULE_ABI, ModuleContext
from ..extensions.registry import ModuleRegistry
from ..services.archive import Archive
from ..services.registry import ServiceRegistry
from ..services.settings import Settings
from ..services.updates import Updates
from .devices import DeviceRegistry, TextConsole
from .platform import Platform
from .scheduler import Scheduler
from ..storage.storage import Storage


class Kernel:
    def __init__(self, data_root=None, modules_path=None, max_steps=10000, event_limit=1000):
        self.platform = Platform()
        self.storage = Storage(None if data_root is None else disk.DiskBackend(data_root))
        self.scheduler = Scheduler()
        self.devices = DeviceRegistry()
        self.console = TextConsole()
        self.devices.register('console', self.console)
        self.events = EventLog(self.storage, system.now_utc, event_limit)
        self.services = ServiceRegistry()
        self.modules = ModuleRegistry(ModuleContext(self.storage, self.services, self.events, self.platform))
        self.language = Interpreter(max_steps)
        self.modules_path = modules_path
        self.state = 'created'

    def start(self):
        if self.state != 'created':
            raise RuntimeError('kernel can only start once')
        self.services.register('settings', Settings())
        self.services.register('archive', Archive(self.storage))
        self.services.register('updates', Updates())
        self.state = 'running'
        self.events.record('kernel', 'started on host Python; no firmware boot occurred')
        if self.modules_path is not None:
            self.reload_modules()

    def reload_modules(self):
        failures = self.modules.discover(self.modules_path)
        for label, reason in sorted(failures.items()):
            self.events.record('kernel', 'module ' + label + ' not loaded: ' + reason)
        return failures

    def stop(self):
        if self.state != 'running':
            raise RuntimeError('kernel is not running')
        self.scheduler.cancel_all()
        self.events.record('kernel', 'stopped')
        self.state = 'stopped'

    def run_file(self, path):
        return self.language.run(self.storage.read(path))

    def describe(self):
        return {'state': self.state, 'platform': self.platform.describe(),
                'module_abi': MODULE_ABI, 'storage': self.storage.describe(),
                'services': self.services.names(),
                'modules': self.modules.names(), 'events': self.events.total}
