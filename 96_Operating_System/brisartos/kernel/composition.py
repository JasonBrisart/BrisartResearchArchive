r"""
File: brisartos/kernel/composition.py

Purpose
-------
Assemble concrete runtime components and built-in services in one explicit
composition function.

Public interface:
- class RuntimeComponents -- An explicit bundle of the nine runtime component
  objects.
- RuntimeComponents(storage, scheduler, devices, console, events, services,
  modules, language, platform) -- Bind the supplied runtime components without
  starting them.
- build_runtime(data_root=None, modules_path=None, max_steps=10000,
  event_limit=1000) -- Construct adapters, components and registered built-in
  services.

Design notes:

The builder wires adapters and domain objects without starting them. Kernel
owns lifecycle and schema initialization. Disk and memory runtimes share
serialization behavior, but only disk-backed files survive a new instance.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.events.events (brisartos/events/events.py)
- brisartos.extensions.api (brisartos/extensions/api.py)
- brisartos.extensions.registry (brisartos/extensions/registry.py)
- brisartos.host.disk (brisartos/host/disk.py)
- brisartos.host.serialization (brisartos/host/serialization.py)
- brisartos.host.system (brisartos/host/system.py)
- brisartos.language.interpreter (brisartos/language/interpreter.py)
- brisartos.machine.devices (brisartos/machine/devices.py)
- brisartos.machine.platform (brisartos/machine/platform.py)
- brisartos.machine.scheduler (brisartos/machine/scheduler.py)
- brisartos.services.archive (brisartos/services/archive.py)
- brisartos.services.registry (brisartos/services/registry.py)
- brisartos.services.settings (brisartos/services/settings.py)
- brisartos.services.updates (brisartos/services/updates.py)
- brisartos.storage.storage (brisartos/storage/storage.py)
Standard library: none.
Imported by:
- brisartos/kernel/kernel.py
Covered by tests: brisartos/kernel/tests/test_architecture.py.

Settings / parameters
---------------------
Constructor arguments select the supplied components and policies; no
module-level configuration is defined.

Edge cases
----------
Invalid inputs are rejected before the documented operation; backend and
callback failures propagate unless explicitly collected.

Known limitations
-----------------
- No generic dependency-injection container or automatic plugin wiring is
  provided.
- Injected components are trusted to implement the documented duck-typed
  interfaces.

Examples
--------
Run from the repository root.

::

    from brisartos.kernel.composition import build_runtime
    c = build_runtime()
    assert c.services.names() == ['archive', 'settings', 'updates']
    assert c.modules.context.accepting is False
"""
from ..host import disk, system, serialization
from ..storage.storage import Storage
from ..events.events import EventLog
from ..extensions.api import ModuleContext
from ..extensions.registry import ModuleRegistry
from ..language.interpreter import Interpreter
from ..services.registry import ServiceRegistry
from ..services.settings import Settings
from ..services.archive import Archive
from ..services.updates import Updates
from ..machine.devices import DeviceRegistry, TextConsole
from ..machine.platform import Platform
from ..machine.scheduler import Scheduler

class RuntimeComponents:
    def __init__(self, storage, scheduler, devices, console, events, services, modules, language, platform):
        self.storage, self.scheduler, self.devices = storage, scheduler, devices
        self.console, self.events, self.services = console, events, services
        self.modules, self.language, self.platform = modules, language, platform

def build_runtime(data_root=None, modules_path=None, max_steps=10000, event_limit=1000):
    storage = Storage(None if data_root is None else disk.DiskBackend(data_root))
    platform = Platform()
    events = EventLog(storage, system.now_utc, event_limit)
    services = ServiceRegistry(events)
    encode, decode = serialization.encode_mapping, serialization.decode_mapping
    services.register('settings', Settings(storage, encode, decode), persistent=data_root is not None)
    services.register('archive', Archive(storage, encode, decode), persistent=data_root is not None)
    services.register('updates', Updates(storage, encode, decode), persistent=data_root is not None)
    devices, console = DeviceRegistry(), TextConsole()
    devices.register('console', console)
    context = ModuleContext(storage, services, events, platform)
    context.close()
    return RuntimeComponents(storage, Scheduler(events), devices, console, events, services,
                             ModuleRegistry(context), Interpreter(max_steps), platform)
