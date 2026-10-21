r"""
File: brisartos/services/tests/test_services.py

Purpose
-------
Exercise service-name registration, metadata, settings snapshots, protected-log
archive restoration and unapplied update staging.

Verifies: brisartos/host/serialization.py, brisartos/services/archive.py,
brisartos/services/registry.py, brisartos/services/settings.py,
brisartos/services/updates.py, brisartos/storage/schema.py,
brisartos/storage/storage.py, version.py.

Contains 13 test case(s) across 5 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.host.serialization (brisartos/host/serialization.py)
- brisartos.services.archive (brisartos/services/archive.py)
- brisartos.services.registry (brisartos/services/registry.py)
- brisartos.services.settings (brisartos/services/settings.py)
- brisartos.services.updates (brisartos/services/updates.py)
- brisartos.storage.schema (brisartos/storage/schema.py)
- brisartos.storage.storage (brisartos/storage/storage.py)
- version (version.py)
Standard library: unittest.
Discovered and run by run.py test (and by python -m unittest discover -s
brisartos/services/tests); nothing imports it.

Settings / parameters
---------------------
No module-level configuration is defined.

Inputs and component instances are created inside the individual test methods;
this file defines no shared setUp or tearDown method.

Edge cases
----------
The updates service is checked to report applied and authenticated as False and
never to run what it stages.

RegistryTests:
- Register get and reject duplicates.
- Names must be safe.
- Describe.
SettingsTests:
- Round trip.
- Snapshot is a copy.
ArchiveTests:
- Save and restore.
- Logs are never rolled back.
- Snapshots do not contain logs.
UpdatesTests:
- Stage never applies.
StatePersistenceTests:
- Each persistent service writes one state document.
- Serialization callbacks are required when storage is given.
- Archive callbacks are all or nothing.
- A second instance loads what the first wrote.

Known limitations
-----------------
- Services are tested in memory; nothing here checks persistence because the
  services keep no state on disk.
- Passing proves only the 13 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
Run from the repository root.

::

    python -B -m unittest discover -s brisartos/services/tests -p test_services.py
"""

import unittest

from brisartos.host.serialization import decode_mapping, encode_mapping
from brisartos.storage.schema import ARCHIVE_PATH, PROTECTED_PREFIXES, SETTINGS_PATH, UPDATES_PATH
from brisartos.storage.storage import Storage
from brisartos.services.archive import PROTECTED, Archive
from brisartos.services.registry import ServiceRegistry
from brisartos.services.settings import Settings
from brisartos.services.updates import Updates
from version import __version__


class RegistryTests(unittest.TestCase):
    def test_register_get_and_reject_duplicates(self):
        registry = ServiceRegistry()
        settings = Settings()
        registry.register('settings', settings)
        self.assertIs(registry.get('settings'), settings)
        with self.assertRaises(ValueError):
            registry.register('settings', Settings())
        with self.assertRaises(KeyError):
            registry.get('missing')

    def test_names_must_be_safe(self):
        registry = ServiceRegistry()
        for bad in ('', 'a b', 'a/b', '../x', None):
            with self.assertRaises(ValueError):
                registry.register(bad, Settings())

    def test_describe(self):
        registry = ServiceRegistry()
        registry.register('settings', Settings())
        registry.register('plain', object())
        self.assertEqual(registry.describe('settings'),
                         {'name': 'settings', 'version': __version__, 'status': 'offline', 'class': 'Settings', 'state': 'registered', 'persistent': False})
        self.assertEqual(registry.describe('plain')['status'], 'no status')
        self.assertEqual(registry.names(), ['plain', 'settings'])


class SettingsTests(unittest.TestCase):
    def test_round_trip(self):
        settings = Settings()
        settings.set('theme', 'plain')
        self.assertEqual(settings.get('theme'), 'plain')
        self.assertEqual(settings.get('missing', 'default'), 'default')
        self.assertEqual(settings.snapshot(), {'theme': 'plain'})
        self.assertEqual(settings.delete('theme'), 'plain')
        with self.assertRaises(KeyError):
            settings.delete('theme')
        with self.assertRaises(ValueError):
            settings.set('', 1)

    def test_snapshot_is_a_copy(self):
        settings = Settings()
        settings.set('a', 1)
        settings.snapshot()['a'] = 2
        self.assertEqual(settings.get('a'), 1)


class ArchiveTests(unittest.TestCase):
    def test_save_and_restore(self):
        storage = Storage()
        archive = Archive(storage)
        storage.write('/a', 'one')
        archive.save('first')
        storage.write('/a', 'two')
        storage.write('/b', 'new')
        archive.restore('first')
        self.assertEqual(storage.snapshot(), {'/a': 'one'})
        self.assertEqual(archive.names(), ['first'])
        with self.assertRaises(KeyError):
            archive.restore('missing')
        with self.assertRaises(ValueError):
            archive.save('')

    def test_logs_are_never_rolled_back(self):
        storage = Storage()
        archive = Archive(storage)
        storage.write('/work/a.txt', 'one')
        storage.append('/logs/kernel.log', 'before save\n')
        archive.save('first')
        storage.append('/logs/kernel.log', 'after save\n')
        storage.write('/work/a.txt', 'two')
        archive.restore('first')
        self.assertEqual(storage.read('/work/a.txt'), 'one')
        self.assertEqual(storage.read('/logs/kernel.log'), 'before save\nafter save\n')

    def test_snapshots_do_not_contain_logs(self):
        self.assertEqual(PROTECTED, ('/logs', '/system'))
        storage = Storage()
        storage.write('/logs/k.log', 'x')
        storage.write('/a', 'y')
        archive = Archive(storage)
        archive.save('s')
        storage.delete('/a')
        archive.restore('s')
        self.assertEqual(storage.list_files(), ['/a', '/logs/k.log'])


class UpdatesTests(unittest.TestCase):
    def test_stage_never_applies(self):
        updates = Updates()
        updates.stage('candidate', 'x = 1')
        self.assertEqual(updates.inspect('candidate'),
                         {'name': 'candidate', 'source': 'x = 1', 'applied': False, 'authenticated': False})
        with self.assertRaises(ValueError):
            updates.stage('candidate', 'x = 2')
        updates.discard('candidate')
        self.assertEqual(updates.names(), [])
        with self.assertRaises(KeyError):
            updates.inspect('candidate')
        with self.assertRaises(ValueError):
            updates.stage('', 'x')


class StatePersistenceTests(unittest.TestCase):
    def test_each_persistent_service_writes_one_state_document(self):
        storage = Storage()
        settings = Settings(storage, encode_mapping, decode_mapping)
        archive = Archive(storage, encode_mapping, decode_mapping)
        updates = Updates(storage, encode_mapping, decode_mapping)
        for service in (settings, archive, updates):
            service.start()
        settings.set('a', 1)
        storage.write('/work.txt', 'x')
        archive.save('s')
        updates.stage('u', 'pass')
        for path, kind in ((SETTINGS_PATH, 'settings'), (ARCHIVE_PATH, 'archive'), (UPDATES_PATH, 'updates')):
            self.assertEqual(decode_mapping(storage.read(path))['kind'], kind)
        self.assertEqual(sorted(storage.list_files(PROTECTED_PREFIXES[1])), sorted([SETTINGS_PATH, ARCHIVE_PATH, UPDATES_PATH]))

    def test_serialization_callbacks_are_required_when_storage_is_given(self):
        with self.assertRaises(ValueError):
            Settings(Storage())
        with self.assertRaises(ValueError):
            Updates(Storage())

    def test_archive_callbacks_are_all_or_nothing(self):
        for pair in ((encode_mapping, None), (None, decode_mapping)):
            with self.assertRaises(ValueError):
                Archive(Storage(), *pair)

    def test_a_second_instance_loads_what_the_first_wrote(self):
        storage = Storage()
        first = Settings(storage, encode_mapping, decode_mapping)
        first.start()
        first.set('theme', 'plain')
        second = Settings(storage, encode_mapping, decode_mapping)
        second.start()
        self.assertEqual(second.get('theme'), 'plain')


if __name__ == '__main__':
    unittest.main()
