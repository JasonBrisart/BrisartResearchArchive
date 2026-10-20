r"""
File: brisartos/extensions/api.py

Purpose
-------
Validate module permission declarations and provide permission-gated access to
logging, module-local files, identifiers, platform facts and named services.

Public interface:
- check_permissions(permissions) -- Validate a declared permission list and
  return it sorted and de-duplicated; refuse a bare string and unknown names.
- class AccessDenied(PermissionError) -- Raised for anything a module did not
  declare; a subclass of the built-in PermissionError.
- class ModuleAPI -- The view of the system that one module receives, limited
  to its declared permissions.
- ModuleAPI(kernel, name, permissions) -- Bind a kernel, a safe module name and
  a permission set.
- ModuleAPI.require(permission) -- Raise AccessDenied unless the module
  declared a permission.
- ModuleAPI.now_utc() -- Return the current UTC time; needs no permission.
- ModuleAPI.available_services() -- Return the names of every registered
  service; needs no permission.
- ModuleAPI.log(message) -- Add a line to the module's own log (needs log).
- ModuleAPI.write_text(filename, text) -- Write a file inside /modules/NAME/
  and return its full path (needs storage).
- ModuleAPI.read_text(filename) -- Return a file from the module's own folder,
  or None when it does not exist (needs storage).
- ModuleAPI.list_files() -- Return the names of the module's own files (needs
  storage).
- ModuleAPI.new_object_id() -- Return 32 random hexadecimal characters (needs
  object_id).
- ModuleAPI.platform_info() -- Return the platform facts (needs platform_info).
- ModuleAPI.get_service(name) -- Return one live service (needs service:NAME
  for that name).

Design notes:

check_permissions validates supported declaration containers and permission
names, returning a sorted tuple. ModuleAPI itself stores its supplied
permissions as a frozenset; direct construction does not call that validator.
Its file methods prepend the module namespace after path normalization. These
checks constrain API use, not the capabilities of arbitrary code running in the
same process.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.common.names (brisartos/common/names.py)
- brisartos.host.system (brisartos/host/system.py)
Standard library: none.
Imported by:
- brisartos/extensions/registry.py
- brisartos/kernel/kernel.py
Covered by tests: brisartos/extensions/tests/test_api.py,
brisartos/extensions/tests/test_registry.py,
brisartos/kernel/tests/test_kernel.py.

Settings / parameters
---------------------
- MODULE_ABI = 'brisartos.module.v1' -- The compatibility string every module
  must declare.
- PERMISSIONS = ('log', 'storage', 'object_id', 'platform_info') -- The fixed
  permissions; service:NAME is accepted in addition.
- SERVICE_PREFIX = 'service:' -- Prefix of the per-service permission.

Edge cases
----------
A missing permission raises AccessDenied. An unsafe module name raises
ValueError at construction, and so does a path containing a parent-traversal
component (..). An unknown service raises KeyError.

- check_permissions() raises TypeError: "permissions must be a tuple of names,
  for example ("log",), not {...}"
- check_permissions() raises ValueError: "unknown permission: {...} (known:
  {...}, service:NAME)"
- ModuleAPI.require() raises AccessDenied: "module {...} lacks permission
  {...}"

Known limitations
-----------------
- Permissions catch mistakes, not hostile code: a module is ordinary Python and
  can import anything and read any file the process can.
- The ABI is a single string, so there is no version negotiation between the
  system and a module.

Examples
--------
Run from the repository root.

::

    from brisartos.kernel.kernel import Kernel
    from brisartos.extensions.api import AccessDenied, ModuleAPI

    kernel = Kernel()
    kernel.start()
    api = ModuleAPI(kernel, 'demo', ('storage',))
    assert api.write_text('a.txt', 'hi') == '/modules/demo/a.txt'
    try:
        api.new_object_id()
    except AccessDenied:
        pass
    else:
        raise AssertionError('object_id was not declared')
"""

from ..common.names import require_name
from ..host import system

MODULE_ABI = 'brisartos.module.v1'
PERMISSIONS = ('log', 'storage', 'object_id', 'platform_info')
SERVICE_PREFIX = 'service:'


def check_permissions(permissions):
    if isinstance(permissions, str) or not isinstance(permissions, (tuple, list, set, frozenset)):
        raise TypeError('permissions must be a tuple of names, for example ("log",), not '
                        + type(permissions).__name__)
    for permission in permissions:
        if permission in PERMISSIONS:
            continue
        if isinstance(permission, str) and permission.startswith(SERVICE_PREFIX):
            require_name(permission[len(SERVICE_PREFIX):], 'service name in permission')
            continue
        raise ValueError('unknown permission: ' + repr(permission) + ' (known: '
                         + ', '.join(PERMISSIONS) + ', service:NAME)')
    return tuple(sorted(set(permissions)))


class AccessDenied(PermissionError):
    pass


class ModuleAPI:
    def __init__(self, kernel, name, permissions):
        self._kernel = kernel
        self.name = require_name(name, 'module name')
        self.permissions = frozenset(permissions)

    def require(self, permission):
        if permission not in self.permissions:
            raise AccessDenied('module ' + repr(self.name) + ' lacks permission ' + repr(permission))

    def now_utc(self):
        return system.now_utc()

    def available_services(self):
        return self._kernel.services.names()

    def log(self, message):
        self.require('log')
        self._kernel.log(self.name, message)

    def _path(self, filename):
        return '/modules/' + self.name + self._kernel.storage.normalize(filename)

    def write_text(self, filename, text):
        self.require('storage')
        return self._kernel.storage.write(self._path(filename), text)

    def read_text(self, filename):
        self.require('storage')
        path = self._path(filename)
        if not self._kernel.storage.exists(path):
            return None
        return self._kernel.storage.read(path)

    def list_files(self):
        self.require('storage')
        prefix = '/modules/' + self.name + '/'
        return [path[len(prefix):] for path in self._kernel.storage.list_files(prefix)]

    def new_object_id(self):
        self.require('object_id')
        return system.new_id()

    def platform_info(self):
        self.require('platform_info')
        return self._kernel.platform.describe()

    def get_service(self, name):
        self.require('service:' + name)
        return self._kernel.services.get(name)
