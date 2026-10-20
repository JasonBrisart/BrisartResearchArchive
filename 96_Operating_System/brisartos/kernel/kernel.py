r"""
File: brisartos/kernel/kernel.py

Purpose
-------
Compose the BrisartOS runtime and coordinate its one-way lifecycle, module
discovery, event recording and stored-program execution.

Public interface:
- class Kernel -- The composition root: storage, object memory, scheduler,
  devices, services, modules, language and platform facts.
- Kernel(data_root=None, modules_path=None, object_capacity=1024,
  max_steps=10000, event_limit=1000) -- Build every component; data_root
  selects disk storage, modules_path a folder of modules to discover.
- Kernel.start() -- Register the settings, archive and updates services, log
  the start and discover modules.
- Kernel.reload_modules() -- Rediscover modules, log each failure and return
  the failures mapping.
- Kernel.stop() -- Cancel every waiting task and log the stop.
- Kernel.log(source, message) -- Record an event in memory and append a line to
  /logs/SOURCE.log.
- Kernel.run_file(path) -- Run a stored file with the restricted language and
  return its result.
- Kernel.describe() -- Return the state, platform facts, ABI, storage, memory,
  services, modules and event count.

Design notes:

Construction selects a storage backend and creates the component objects. start
registers three services before logging and discovery; stop cancels waiting
tasks before logging and changing state. log records an in-memory event before
appending its file line, so a failed append can leave the two records
inconsistent. Only the recent-event list is bounded; file logs are not trimmed.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.common.names (brisartos/common/names.py)
- brisartos.host.disk (brisartos/host/disk.py)
- brisartos.host.system (brisartos/host/system.py)
- brisartos.kernel.devices (brisartos/kernel/devices.py)
- brisartos.kernel.memory (brisartos/kernel/memory.py)
- brisartos.kernel.platform (brisartos/kernel/platform.py)
- brisartos.kernel.scheduler (brisartos/kernel/scheduler.py)
- brisartos.kernel.storage (brisartos/kernel/storage.py)
- brisartos.language.interpreter (brisartos/language/interpreter.py)
- brisartos.modules.api (brisartos/modules/api.py)
- brisartos.modules.registry (brisartos/modules/registry.py)
- brisartos.services.archive (brisartos/services/archive.py)
- brisartos.services.registry (brisartos/services/registry.py)
- brisartos.services.settings (brisartos/services/settings.py)
- brisartos.services.updates (brisartos/services/updates.py)
Standard library: none.
Imported by:
- brisartos/shell/console.py
Covered by tests: brisartos/kernel/tests/test_kernel.py,
brisartos/modules/tests/test_api.py, brisartos/modules/tests/test_registry.py,
brisartos/shell/tests/test_shell.py.

Settings / parameters
---------------------
Kernel(data_root=None, modules_path=None, object_capacity=1024,
max_steps=10000, event_limit=1000). With data_root=None files live in memory;
with a folder they live on disk there. With modules_path=None no modules are
discovered.

Edge cases
----------
A module that fails to load is logged as "module NAME not loaded: REASON" and
never stops start. run_file lets storage and language errors pass through to
the caller.

- Kernel.__init__() raises ValueError: "event_limit must be a positive integer"
- Kernel.start() raises RuntimeError: "kernel can only start once"
- Kernel.stop() raises RuntimeError: "kernel is not running"

Known limitations
-----------------
- A stopped kernel cannot restart; build a new one.
- Everything runs in one host Python process with no isolation between the
  kernel, the shell and modules.
- Settings, snapshots and update candidates live in memory only, so they are
  not restored when a new kernel opens the same data folder.
- Log files are never rotated or trimmed.

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

from ..common.names import require_name
from ..host import disk, system
from ..language.interpreter import Interpreter
from ..modules.api import MODULE_ABI
from ..modules.registry import ModuleRegistry
from ..services.archive import Archive
from ..services.registry import ServiceRegistry
from ..services.settings import Settings
from ..services.updates import Updates
from .devices import DeviceRegistry, TextConsole
from .memory import ObjectMemory
from .platform import Platform
from .scheduler import Scheduler
from .storage import Storage


class Kernel:
    def __init__(self, data_root=None, modules_path=None, object_capacity=1024,
                 max_steps=10000, event_limit=1000):
        if type(event_limit) is not int or event_limit < 1:
            raise ValueError('event_limit must be a positive integer')
        self.platform = Platform()
        self.storage = Storage(None if data_root is None else disk.DiskBackend(data_root))
        self.memory = ObjectMemory(object_capacity)
        self.scheduler = Scheduler()
        self.devices = DeviceRegistry()
        self.console = TextConsole()
        self.devices.register('console', self.console)
        self.services = ServiceRegistry()
        self.modules = ModuleRegistry(self)
        self.language = Interpreter(max_steps)
        self.modules_path = modules_path
        self.event_limit = event_limit
        self.events = []
        self._event_count = 0
        self.state = 'created'

    def start(self):
        if self.state != 'created':
            raise RuntimeError('kernel can only start once')
        self.services.register('settings', Settings())
        self.services.register('archive', Archive(self.storage))
        self.services.register('updates', Updates())
        self.state = 'running'
        self.log('kernel', 'started on host Python; no firmware boot occurred')
        if self.modules_path is not None:
            self.reload_modules()

    def reload_modules(self):
        failures = self.modules.discover(self.modules_path)
        for label, reason in sorted(failures.items()):
            self.log('kernel', 'module ' + label + ' not loaded: ' + reason)
        return failures

    def stop(self):
        if self.state != 'running':
            raise RuntimeError('kernel is not running')
        self.scheduler.cancel_all()
        self.log('kernel', 'stopped')
        self.state = 'stopped'

    def log(self, source, message):
        require_name(source, 'log source')
        stamp = system.now_utc()
        self._event_count += 1
        self.events.append({'sequence': self._event_count, 'time': stamp,
                            'source': source, 'message': message})
        if len(self.events) > self.event_limit:
            del self.events[0]
        self.storage.append('/logs/' + source + '.log', stamp + ' ' + source + ': ' + message + '\n')

    def run_file(self, path):
        return self.language.run(self.storage.read(path))

    def describe(self):
        return {'state': self.state, 'platform': self.platform.describe(),
                'module_abi': MODULE_ABI, 'storage': self.storage.describe(),
                'memory': self.memory.status(), 'services': self.services.names(),
                'modules': self.modules.names(), 'events': self._event_count}
