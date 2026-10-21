r"""
File: brisartos/services/registry.py

Purpose
-------
Register named service records, start in insertion order and collect
reverse-order shutdown failures.

Public interface:
- class ServiceRecord -- Lifecycle metadata and the live service reference.
- ServiceRecord(name, service, persistent=False) -- Bind a name, service and
  persistence declaration.
- class ServiceRegistry -- A named service table with ordered lifecycle
  coordination.
- ServiceRegistry(events=None) -- Create a registry with optional structured
  event recording.
- ServiceRegistry.register(name, service, persistent=False) -- Validate and
  register a service in startup order.
- ServiceRegistry.get(name) -- Return the underlying live service for trusted
  runtime callers.
- ServiceRegistry.names() -- Return sorted registered names.
- ServiceRegistry.start_all() -- Start in registration order; unwind attempted
  starts on failure.
- ServiceRegistry.stop_all() -- Stop in reverse order and return collected
  failure records.
- ServiceRegistry.describe(name) -- Return metadata including lifecycle state
  and persistence.

Design notes:

Lifecycle hooks are optional for simple third-party service objects. Failed
startup cleans up attempted services and re-raises the original failure;
shutdown continues after individual hook or event failures.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.common.names (brisartos/common/names.py)
Standard library: none.
Imported by:
- brisartos/kernel/composition.py
Covered by tests: brisartos/extensions/tests/test_api.py,
brisartos/kernel/tests/test_architecture.py,
brisartos/services/tests/test_services.py.

Settings / parameters
---------------------
Constructor arguments select the supplied components and policies; no
module-level configuration is defined.

Edge cases
----------
Invalid inputs are rejected before the documented operation; backend and
callback failures propagate unless explicitly collected.

- ServiceRegistry.register() raises ValueError: "service already registered:
  {...}"
- ServiceRegistry.register() raises ValueError: "service object required"
- ServiceRegistry.get() raises KeyError: "unknown service: {...}"
- ServiceRegistry.start_all() raises RuntimeError: "service already started:
  {...}"
- ServiceRegistry.start_all() re-raises the active exception
- ServiceRegistry.start_all() catches BaseException -- Collect the failure as
  documented and continue cleanup or report it to the caller.
- ServiceRegistry.stop_all() catches BaseException -- Collect the failure as
  documented and continue cleanup or report it to the caller.

Known limitations
-----------------
- Status text remains a service-supplied label, not an independent health
  probe.
- Cleanup cannot interrupt a hook that never returns.

Examples
--------
Run from the repository root.

::

    from brisartos.services.registry import ServiceRegistry
    from brisartos.services.settings import Settings
    r = ServiceRegistry()
    r.register('settings', Settings())
    r.start_all()
    assert r.describe('settings')['state'] == 'running'
    assert r.stop_all() == []
"""
from ..common.names import require_name

class ServiceRecord:
    def __init__(self, name, service, persistent=False):
        self.name, self.service, self.persistent = name, service, bool(persistent)
        self.state = 'registered'

class ServiceRegistry:
    def __init__(self, events=None):
        self._services = {}
        self._started = []
        self._events = events
        self.lifecycle_errors = []
    def register(self, name, service, persistent=False):
        require_name(name, 'service name')
        if name in self._services:
            raise ValueError('service already registered: ' + name)
        if service is None:
            raise ValueError('service object required')
        self._services[name] = ServiceRecord(name, service, persistent)
    def get(self, name):
        if name not in self._services:
            raise KeyError('unknown service: ' + str(name))
        return self._services[name].service
    def names(self):
        return sorted(self._services)
    def start_all(self):
        try:
            for name, record in self._services.items():
                if record.state != 'registered':
                    raise RuntimeError('service already started: ' + name)
                self._started.append(name)
                record.state = 'starting'
                callback = getattr(record.service, 'start', None)
                if callback is not None:
                    callback()
                record.state = 'running'
                if self._events is not None:
                    self._events.record('services', 'started ' + name, kind='service.started', details={'service': name})
        except BaseException:
            self.lifecycle_errors.extend(self.stop_all())
            raise
    def stop_all(self):
        failures = []
        for name in reversed(self._started):
            record = self._services[name]
            try:
                callback = getattr(record.service, 'stop', None)
                if callback is not None:
                    callback()
                record.state = 'stopped'
            except BaseException as error:
                record.state = 'failed'
                failures.append({'service': name, 'error': type(error).__name__ + ': ' + str(error)})
            try:
                if self._events is not None:
                    self._events.record('services', 'stopped ' + name, kind='service.stopped', details={'service': name, 'state': record.state})
            except BaseException as error:
                failures.append({'service': name, 'error': 'logging: ' + str(error)})
        self._started = []
        return failures
    def describe(self, name):
        service = self.get(name)
        record = self._services[name]
        status = service.status() if hasattr(service, 'status') else 'no status'
        return {'name': name, 'version': getattr(service, 'version', 'unknown'),
                'status': status, 'class': type(service).__name__,
                'state': record.state, 'persistent': record.persistent}
