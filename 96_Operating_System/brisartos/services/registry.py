r"""
File: brisartos/services/registry.py

Purpose
-------
Register service objects under validated unique names and expose their live
objects and descriptive metadata.

Public interface:
- class ServiceRegistry -- Holds registered services by name.
- ServiceRegistry.register(name, service) -- Add a service under a unique safe
  name.
- ServiceRegistry.get(name) -- Return the live service or raise KeyError.
- ServiceRegistry.names() -- Return the sorted service names.
- ServiceRegistry.describe(name) -- Return name, version, status and class for
  one service.

Design notes:

The registry validates the name but imposes no interface on the object.
describe calls status when that attribute exists and reads version with a
fallback. A status method can raise, and a non-callable status attribute also
fails; this file does not convert those failures into health information.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.common.names (brisartos/common/names.py)
Standard library: none.
Imported by:
- brisartos/kernel/kernel.py
Covered by tests: brisartos/extensions/tests/test_api.py,
brisartos/services/tests/test_services.py.

Settings / parameters
---------------------
No module-level settings. Names must pass common.names.require_name.

Edge cases
----------
A duplicate name raises ValueError and so does an invalid name; an unknown
service raises KeyError.

- ServiceRegistry.register() raises ValueError: "service already registered:
  {...}"
- ServiceRegistry.get() raises KeyError: "unknown service: {...}"

Known limitations
-----------------
- The status text is whatever the service returns. It is a label, not a health
  check.
- Registration order is not preserved; names() always sorts.

Examples
--------
Run from the repository root.

::

    from brisartos.services.registry import ServiceRegistry
    from brisartos.services.settings import Settings

    registry = ServiceRegistry()
    registry.register('settings', Settings())
    assert registry.names() == ['settings']
    assert registry.describe('settings')['status'] == 'online'
"""

from ..common.names import require_name


class ServiceRegistry:
    def __init__(self):
        self._services = {}

    def register(self, name, service):
        require_name(name, 'service name')
        if name in self._services:
            raise ValueError('service already registered: ' + name)
        self._services[name] = service

    def get(self, name):
        if name not in self._services:
            raise KeyError('unknown service: ' + str(name))
        return self._services[name]

    def names(self):
        return sorted(self._services)

    def describe(self, name):
        service = self.get(name)
        status = service.status() if hasattr(service, 'status') else 'no status'
        return {'name': name, 'version': getattr(service, 'version', 'unknown'),
                'status': status, 'class': type(service).__name__}
