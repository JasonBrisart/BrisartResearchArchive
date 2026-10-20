r"""
File: brisartos/modules/tests/test_registry.py

Purpose
-------
Exercise code registration, discovered modules, reload, logged entry failures,
module metadata and documentation of the module contract.

Verifies: brisartos/kernel/kernel.py, brisartos/modules/api.py,
brisartos/modules/registry.py, version.py.

Contains 18 test case(s) across 3 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.kernel.kernel (brisartos/kernel/kernel.py)
- brisartos.modules.api (brisartos/modules/api.py)
- brisartos.modules.registry (brisartos/modules/registry.py)
- version (version.py)
Standard library: pathlib, tempfile, unittest.
Discovered and run by run.py test (and by python -m unittest discover -s
brisartos/modules/tests); nothing imports it.

Settings / parameters
---------------------
Module fixtures: ROOT, MODULE.

Fixture helpers in this file: RegistryTests: setUp.

Edge cases
----------
Bad modules are written into temporary folders on purpose to exercise each
failure path. A module that raises SystemExit must be logged and the exit still
propagate.

RegistryTests:
- Code module run is logged.
- Failure is logged and raised.
- Exit requests from a module are logged before they propagate.
- Registration rules.
- Names must be safe.
- Permissions are sorted and deduplicated.
- Bad permission lists are refused at registration.
- Display name is kept and defaults to the name.
- Describe does not expose the entry function.
DocumentationTests:
- Every required name is documented.
- Every permission and the abi are documented.
DiscoveryTests:
- Good bad and ignored folders.
- A module with an unsafe name is rejected.
- Duplicate names load first alphabetically.
- A module with a misspelled permission does not load.
- Reload picks up new modules and keeps code modules.
- Permission failure in a module.
- Shipped hello lab runs end to end.

Known limitations
-----------------
- Discovery really executes the module files it finds, so the tests only use
  files they wrote themselves.
- Passing proves only the 18 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
Run from the repository root.

::

    python -B -m unittest discover -s brisartos/modules/tests -p test_registry.py
"""

import tempfile
import unittest
from pathlib import Path

from brisartos.kernel.kernel import Kernel
from brisartos.modules.api import MODULE_ABI, AccessDenied
from brisartos.modules.registry import REQUIRED_NAMES
from version import __version__

ROOT = Path(__file__).resolve().parents[3]

MODULE = '''
MODULE_NAME = "{name}"
MODULE_DISPLAY_NAME = "Test"
MODULE_VERSION = "1"
MODULE_AUTHOR = "Tester"
MODULE_DESCRIPTION = "test module"
MODULE_ABI = "{abi}"
MODULE_PERMISSIONS = {permissions}

def run(api):
    {body}
'''


class ModuleFolder:
    def __init__(self, test):
        self.folder = tempfile.TemporaryDirectory()
        test.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name)

    def add(self, folder, text):
        (self.path / folder).mkdir()
        (self.path / folder / 'module.py').write_text(text)

    def module(self, name, body='return "ok"', permissions='()', abi='brisartos.module.v1'):
        self.add(name, MODULE.format(name=name, body=body, permissions=permissions, abi=abi))


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.kernel = Kernel()
        self.kernel.start()

    def test_code_module_run_is_logged(self):
        self.kernel.modules.register('greeter', lambda api: 'hi')
        self.assertEqual(self.kernel.modules.run('greeter'), 'hi')
        log = self.kernel.storage.read('/logs/greeter.log')
        self.assertIn('module started', log)
        self.assertIn('module finished', log)

    def test_failure_is_logged_and_raised(self):
        def broken(api):
            raise RuntimeError('boom')
        self.kernel.modules.register('broken', broken)
        with self.assertRaises(RuntimeError):
            self.kernel.modules.run('broken')
        self.assertIn('module failed: RuntimeError: boom', self.kernel.storage.read('/logs/broken.log'))

    def test_exit_requests_from_a_module_are_logged_before_they_propagate(self):
        def quitter(api):
            raise SystemExit(3)
        self.kernel.modules.register('quitter', quitter)
        with self.assertRaises(SystemExit):
            self.kernel.modules.run('quitter')
        self.assertIn('module failed: SystemExit: 3', self.kernel.storage.read('/logs/quitter.log'))

    def test_registration_rules(self):
        self.kernel.modules.register('a', lambda api: None)
        with self.assertRaises(ValueError):
            self.kernel.modules.register('a', lambda api: None)
        with self.assertRaises(TypeError):
            self.kernel.modules.register('b', 'not callable')
        with self.assertRaises(KeyError):
            self.kernel.modules.run('missing')
        self.assertEqual(self.kernel.modules.describe('a')['version'], __version__)

    def test_names_must_be_safe(self):
        for bad in ('../x', 'a/b', '', 'a b'):
            with self.assertRaises(ValueError):
                self.kernel.modules.register(bad, lambda api: None)

    def test_permissions_are_sorted_and_deduplicated(self):
        self.kernel.modules.register('p', lambda api: None, ('storage', 'log', 'log'))
        self.assertEqual(self.kernel.modules.describe('p')['permissions'], ('log', 'storage'))

    def test_bad_permission_lists_are_refused_at_registration(self):
        with self.assertRaises(TypeError):
            self.kernel.modules.register('typo', lambda api: None, ('log'))
        with self.assertRaises(ValueError):
            self.kernel.modules.register('typo', lambda api: None, ('storge',))
        self.assertNotIn('typo', self.kernel.modules.names())

    def test_display_name_is_kept_and_defaults_to_the_name(self):
        self.kernel.modules.register('plain', lambda api: None)
        self.kernel.modules.register('fancy', lambda api: None, display_name='Fancy Module')
        self.assertEqual(self.kernel.modules.describe('plain')['display_name'], 'plain')
        self.assertEqual(self.kernel.modules.describe('fancy')['display_name'], 'Fancy Module')

    def test_describe_does_not_expose_the_entry_function(self):
        self.kernel.modules.register('p', lambda api: None)
        self.assertNotIn('entry', self.kernel.modules.describe('p'))


class DocumentationTests(unittest.TestCase):
    PERMISSIONS = ('log', 'storage', 'object_id', 'platform_info', 'service:NAME')

    def pages(self):
        return [(ROOT / 'brisartos' / 'modules' / 'README.md').read_text(encoding='utf-8'),
                (ROOT / 'modules' / 'README.md').read_text(encoding='utf-8')]

    def test_every_required_name_is_documented(self):
        for page in self.pages():
            for name in REQUIRED_NAMES:
                self.assertIn('`' + name + '`', page.replace('`run(api)`', '`run`'), name)

    def test_every_permission_and_the_abi_are_documented(self):
        for page in self.pages():
            for permission in self.PERMISSIONS:
                self.assertIn('`' + permission + '`', page, permission)
            self.assertIn(MODULE_ABI, page)


class DiscoveryTests(unittest.TestCase):
    def test_good_bad_and_ignored_folders(self):
        folder = ModuleFolder(self)
        folder.module('good')
        folder.module('wrong_abi', abi='brisartos.module.v2')
        folder.add('broken', 'raise RuntimeError("fails on import")\n')
        folder.add('incomplete', 'MODULE_NAME = "incomplete"\n')
        (folder.path / 'empty').mkdir()
        (folder.path / 'stray.py').write_text('x = 1\n')
        kernel = Kernel(modules_path=folder.path)
        kernel.start()
        self.assertEqual(kernel.modules.names(), ['good'])
        self.assertEqual(sorted(kernel.modules.failures), ['broken', 'incomplete', 'wrong_abi'])
        self.assertIn('unsupported ABI', kernel.modules.failures['wrong_abi'])
        self.assertIn('missing', kernel.modules.failures['incomplete'])
        self.assertIn('module broken not loaded', kernel.storage.read('/logs/kernel.log'))

    def test_a_module_with_an_unsafe_name_is_rejected(self):
        folder = ModuleFolder(self)
        folder.module('weird', body='return 1')
        text = (folder.path / 'weird' / 'module.py').read_text().replace('"weird"', '"../escape"')
        (folder.path / 'weird' / 'module.py').write_text(text)
        kernel = Kernel(modules_path=folder.path)
        kernel.start()
        self.assertEqual(kernel.modules.names(), [])
        self.assertIn('invalid module name', kernel.modules.failures['weird'])

    def test_duplicate_names_load_first_alphabetically(self):
        folder = ModuleFolder(self)
        folder.module('first')
        folder.add('second', (folder.path / 'first' / 'module.py').read_text())
        kernel = Kernel(modules_path=folder.path)
        kernel.start()
        self.assertEqual(kernel.modules.names(), ['first'])
        self.assertIn('already registered', kernel.modules.failures['second'])

    def test_a_module_with_a_misspelled_permission_does_not_load(self):
        folder = ModuleFolder(self)
        folder.module('typo', permissions='("storge",)')
        folder.module('bare', permissions='("log")')
        kernel = Kernel(modules_path=folder.path)
        kernel.start()
        self.assertEqual(kernel.modules.names(), [])
        self.assertIn('unknown permission', kernel.modules.failures['typo'])
        self.assertIn('TypeError', kernel.modules.failures['bare'])

    def test_reload_picks_up_new_modules_and_keeps_code_modules(self):
        folder = ModuleFolder(self)
        kernel = Kernel(modules_path=folder.path)
        kernel.start()
        kernel.modules.register('code', lambda api: None)
        folder.module('late')
        kernel.reload_modules()
        self.assertEqual(kernel.modules.names(), ['code', 'late'])

    def test_permission_failure_in_a_module(self):
        folder = ModuleFolder(self)
        folder.module('nosy', body='return api.new_object_id()')
        kernel = Kernel(modules_path=folder.path)
        kernel.start()
        with self.assertRaises(AccessDenied):
            kernel.modules.run('nosy')
        self.assertIn('module failed: AccessDenied', kernel.storage.read('/logs/nosy.log'))

    def test_shipped_hello_lab_runs_end_to_end(self):
        kernel = Kernel(modules_path=ROOT / 'modules')
        kernel.start()
        result = kernel.modules.run('hello_lab')
        self.assertIn('/modules/hello_lab/hello.txt', result)
        object_id = kernel.services.get('settings').get('hello_lab.last_id')
        self.assertIn(object_id, kernel.storage.read('/modules/hello_lab/hello.txt'))
        self.assertEqual(kernel.modules.describe('hello_lab')['version'], __version__)
        self.assertEqual(kernel.modules.describe('hello_lab')['display_name'], 'Hello Lab')


if __name__ == '__main__':
    unittest.main()
