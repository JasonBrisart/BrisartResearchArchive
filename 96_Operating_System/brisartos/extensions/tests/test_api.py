r"""
File: brisartos/extensions/tests/test_api.py

Purpose
-------
Exercise module API permission gates, module-local paths, service-specific
access and declaration validation.

Verifies: brisartos/events/events.py, brisartos/extensions/api.py,
brisartos/kernel/kernel.py, brisartos/kernel/platform.py,
brisartos/services/registry.py, brisartos/storage/storage.py.

Contains 12 test case(s) across 1 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.events.events (brisartos/events/events.py)
- brisartos.extensions.api (brisartos/extensions/api.py)
- brisartos.kernel.kernel (brisartos/kernel/kernel.py)
- brisartos.kernel.platform (brisartos/kernel/platform.py)
- brisartos.services.registry (brisartos/services/registry.py)
- brisartos.storage.storage (brisartos/storage/storage.py)
Standard library: unittest.
Discovered and run by run.py test (and by python -m unittest discover -s
brisartos/extensions/tests); nothing imports it.

Settings / parameters
---------------------
No module-level configuration is defined.

Fixture helpers in this file: ModuleAPITests: setUp.

Edge cases
----------
AccessDenied must be a built-in PermissionError, so callers can catch it either
way.

ModuleAPITests:
- Every gated method requires its permission.
- Access denied is a builtin permission error.
- Service permission names the service.
- Storage is confined to the module folder.
- One module cannot see another modules files.
- Module name must be safe.
- Check permissions refuses a bare string.
- Check permissions refuses unknown names.
- Check permissions sorts and deduplicates.
- Permitted calls.
- The api works from a context without a kernel.
- The kernel hands modules a context not itself.

Known limitations
-----------------
- Hostile modules are not tested; modules are trusted code by design.
- Passing proves only the 12 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
Run from the repository root.

::

    python -B -m unittest discover -s brisartos/extensions/tests -p test_api.py
"""

import unittest

from brisartos.kernel.kernel import Kernel
from brisartos.events.events import EventLog
from brisartos.extensions.api import AccessDenied, ModuleAPI, ModuleContext, check_permissions
from brisartos.kernel.platform import Platform
from brisartos.services.registry import ServiceRegistry
from brisartos.storage.storage import Storage


class ModuleAPITests(unittest.TestCase):
    def setUp(self):
        self.kernel = Kernel()
        self.kernel.start()

    def test_every_gated_method_requires_its_permission(self):
        api = ModuleAPI(self.kernel.modules.context, 'demo', ())
        calls = [lambda: api.log('x'), lambda: api.write_text('a', 'x'), lambda: api.read_text('a'),
                 api.list_files, api.new_object_id, api.platform_info,
                 lambda: api.get_service('settings')]
        for call in calls:
            with self.assertRaises(AccessDenied):
                call()

    def test_access_denied_is_a_builtin_permission_error(self):
        self.assertTrue(issubclass(AccessDenied, PermissionError))

    def test_service_permission_names_the_service(self):
        api = ModuleAPI(self.kernel.modules.context, 'demo', ('service:settings',))
        self.assertIsNotNone(api.get_service('settings'))
        with self.assertRaises(AccessDenied):
            api.get_service('archive')

    def test_storage_is_confined_to_the_module_folder(self):
        api = ModuleAPI(self.kernel.modules.context, 'demo', ('storage',))
        self.assertEqual(api.write_text('notes/a.txt', 'x'), '/modules/demo/notes/a.txt')
        self.assertEqual(api.read_text('notes/a.txt'), 'x')
        self.assertIsNone(api.read_text('missing'))
        self.assertEqual(api.list_files(), ['notes/a.txt'])
        with self.assertRaises(ValueError):
            api.write_text('../other/a.txt', 'x')

    def test_one_module_cannot_see_another_modules_files(self):
        ModuleAPI(self.kernel.modules.context, 'one', ('storage',)).write_text('a.txt', 'secret')
        other = ModuleAPI(self.kernel.modules.context, 'two', ('storage',))
        self.assertEqual(other.list_files(), [])
        self.assertIsNone(other.read_text('a.txt'))

    def test_module_name_must_be_safe(self):
        for bad in ('../x', 'a/b', '', 'a b', None):
            with self.assertRaises(ValueError):
                ModuleAPI(self.kernel.modules.context, bad, ('storage',))

    def test_check_permissions_refuses_a_bare_string(self):
        with self.assertRaises(TypeError) as caught:
            check_permissions('log')
        self.assertIn('("log",)', str(caught.exception))

    def test_check_permissions_refuses_unknown_names(self):
        for bad in (('storge',), ('service:',), ('service:../x',), (5,)):
            with self.assertRaises(ValueError):
                check_permissions(bad)

    def test_check_permissions_sorts_and_deduplicates(self):
        self.assertEqual(check_permissions(['storage', 'log', 'log', 'service:settings']),
                         ('log', 'service:settings', 'storage'))

    def test_permitted_calls(self):
        api = ModuleAPI(self.kernel.modules.context, 'demo', ('log', 'object_id', 'platform_info', 'service:settings'))
        api.log('hello')
        self.assertIn('demo: hello', self.kernel.storage.read('/logs/demo.log'))
        self.assertEqual(len(api.new_object_id()), 32)
        self.assertFalse(api.platform_info()['bootable'])
        self.assertIs(api.get_service('settings'), self.kernel.services.get('settings'))
        self.assertEqual(api.available_services(), ['archive', 'settings', 'updates'])
        self.assertTrue(api.now_utc().endswith('+00:00'))

    def test_the_api_works_from_a_context_without_a_kernel(self):
        store = Storage()
        context = ModuleContext(store, ServiceRegistry(), EventLog(store, lambda: 'T'), Platform())
        api = ModuleAPI(context, 'demo', ('log', 'storage', 'platform_info'))
        self.assertEqual(api.write_text('a.txt', 'x'), '/modules/demo/a.txt')
        api.log('hello')
        self.assertEqual(store.read('/logs/demo.log'), 'T demo: hello\n')
        self.assertEqual(api.available_services(), [])
        self.assertFalse(api.platform_info()['bootable'])

    def test_the_kernel_hands_modules_a_context_not_itself(self):
        context = self.kernel.modules.context
        self.assertIsInstance(context, ModuleContext)
        self.assertIs(context.storage, self.kernel.storage)
        self.assertIs(context.services, self.kernel.services)
        self.assertIs(context.events, self.kernel.events)
        self.assertFalse(hasattr(context, 'stop'))


if __name__ == '__main__':
    unittest.main()
