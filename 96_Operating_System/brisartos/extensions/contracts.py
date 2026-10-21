r"""
File: brisartos/extensions/contracts.py

Purpose
-------
Define explicit module API compatibility and narrow service facades without
exposing lifecycle operations.

Public interface:
- check_compatibility(api) -- Validate API name, major and minimum required
  minor; return a tuple.
- class SettingsAccess -- A narrow settings operations facade.
- SettingsAccess(service) -- Bind the underlying settings service.
- SettingsAccess.get(key, default=None) -- Read a setting or default.
- SettingsAccess.set(key, value) -- Write a setting.
- SettingsAccess.delete(key) -- Remove a setting.
- SettingsAccess.snapshot() -- Return the service snapshot.
- class ArchiveAccess -- A narrow archive operations facade.
- ArchiveAccess(service) -- Bind the underlying archive service.
- ArchiveAccess.save(name) -- Save a named user-file snapshot.
- ArchiveAccess.restore(name) -- Restore a named snapshot.
- ArchiveAccess.names() -- Return snapshot names.
- class UpdatesAccess -- A narrow candidate-staging facade.
- UpdatesAccess(service) -- Bind the underlying update service.
- UpdatesAccess.stage(name, source) -- Stage source text without executing it.
- UpdatesAccess.inspect(name) -- Inspect candidate text and fixed false flags.
- UpdatesAccess.discard(name) -- Remove a candidate.
- UpdatesAccess.names() -- Return candidate names.
- service_access(name, service) -- Return the built-in facade or reject an
  unadapted service.

Design notes:

Name and major must match; required minor must not exceed the runtime minor.
Built-in service facades expose only their documented operations. Unknown
services require an explicit new facade rather than returning a live object.

Communication / relationships
-----------------------------
Standard library: none.
Imported by:
- brisartos/extensions/api.py
- brisartos/extensions/registry.py
Covered by tests: brisartos/kernel/tests/test_architecture.py.

Settings / parameters
---------------------
- MODULE_API_NAME = 'brisartos.module' -- Fixed local policy used by the
  operations documented above.
- MODULE_API_MAJOR = 1 -- Fixed local policy used by the operations documented
  above.
- MODULE_API_MINOR = 0 -- Fixed local policy used by the operations documented
  above.

Edge cases
----------
Invalid inputs are rejected before the documented operation; backend and
callback failures propagate unless explicitly collected.

- check_compatibility() raises ValueError: "module API must be (name, major,
  minor)"
- check_compatibility() raises ValueError: "module API versions must be
  nonnegative integers"
- check_compatibility() raises ValueError: "unsupported module API: {...}"
- service_access() raises ValueError: "no module facade for service: {...}"

Known limitations
-----------------
- Facades reduce accidental coupling; private attributes remain accessible to
  trusted Python code.
- Legacy ABI declarations are accepted by the registry but do not prove
  compatibility with pre-refactor releases.

Examples
--------
Run from the repository root.

::

    from brisartos.extensions.contracts import check_compatibility
    assert check_compatibility(('brisartos.module', 1, 0)) == ('brisartos.module', 1, 0)
"""
MODULE_API_NAME = 'brisartos.module'
MODULE_API_MAJOR = 1
MODULE_API_MINOR = 0


def check_compatibility(api):
    if not isinstance(api, (tuple, list)) or len(api) != 3:
        raise ValueError('module API must be (name, major, minor)')
    name, major, minor = api
    if type(major) is not int or type(minor) is not int or major < 0 or minor < 0:
        raise ValueError('module API versions must be nonnegative integers')
    if name != MODULE_API_NAME or major != MODULE_API_MAJOR or minor > MODULE_API_MINOR:
        raise ValueError('unsupported module API: ' + str(api))
    return (name, major, minor)

class SettingsAccess:
    def __init__(self, service):
        self._service = service
    def get(self, key, default=None):
        return self._service.get(key, default)
    def set(self, key, value):
        return self._service.set(key, value)
    def delete(self, key):
        return self._service.delete(key)
    def snapshot(self):
        return self._service.snapshot()

class ArchiveAccess:
    def __init__(self, service):
        self._service = service
    def save(self, name):
        return self._service.save(name)
    def restore(self, name):
        return self._service.restore(name)
    def names(self):
        return self._service.names()

class UpdatesAccess:
    def __init__(self, service):
        self._service = service
    def stage(self, name, source):
        return self._service.stage(name, source)
    def inspect(self, name):
        return self._service.inspect(name)
    def discard(self, name):
        return self._service.discard(name)
    def names(self):
        return self._service.names()


def service_access(name, service):
    if name == 'settings':
        return SettingsAccess(service)
    if name == 'archive':
        return ArchiveAccess(service)
    if name == 'updates':
        return UpdatesAccess(service)
    raise ValueError('no module facade for service: ' + name)
