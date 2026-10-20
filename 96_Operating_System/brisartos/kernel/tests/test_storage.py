r"""
File: brisartos/kernel/tests/test_storage.py

Purpose
-------
Apply a shared file-storage contract to memory and disk backends, including
restore validation, protected prefixes and file-versus-directory replacement.

Verifies: brisartos/host/disk.py, brisartos/kernel/storage.py.

Contains 30 test case(s) across 2 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.host.disk (brisartos/host/disk.py)
- brisartos.kernel.storage (brisartos/kernel/storage.py)
Standard library: pathlib, tempfile, unittest.
Discovered and run by run.py test (and by python -m unittest discover -s
brisartos/kernel/tests); nothing imports it.

Settings / parameters
---------------------
No module-level configuration is defined.

Fixture helpers in this file: StorageContract: make, setUp. MemoryStorageTests:
make. DiskStorageTests: make.

Edge cases
----------
A rejected restore must change nothing; the contract checks that on both
backends. Protected folders are excluded from snapshots and left alone by
restore.

StorageContract:
- Write read round trip.
- Text is stored exactly.
- Missing file raises file not found.
- Append creates then extends.
- List files sorted and by folder.
- Exists and delete.
- A path cannot be both file and folder.
- Snapshot restore replaces everything.
- Restore can swap a file for a folder.
- Snapshot excludes and restore keeps protected folders.
- Protected paths in a snapshot are ignored on restore.
- Invalid restore changes nothing.
- Rejects bad paths and text.
- Describe counts files.
MemoryStorageTests:
- Default backend is memory.
DiskStorageTests:
- Files land on disk and survive a new storage.

Known limitations
-----------------
- Concurrency, very large files and non-UTF-8 content are not covered.
- Passing proves only the 16 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
Run from the repository root.

::

    python -B -m unittest discover -s brisartos/kernel/tests -p test_storage.py
"""

import tempfile
import unittest
from pathlib import Path

from brisartos.host.disk import DiskBackend
from brisartos.kernel.storage import MemoryBackend, Storage


class StorageContract:
    def make(self):
        raise NotImplementedError

    def setUp(self):
        self.storage = self.make()

    def test_write_read_round_trip(self):
        self.assertEqual(self.storage.write('notes/a.txt', 'one'), '/notes/a.txt')
        self.assertEqual(self.storage.read('/notes/a.txt'), 'one')

    def test_text_is_stored_exactly(self):
        text = 'a\r\nb\rc\n\u00e9\n'
        self.storage.write('/t.txt', text)
        self.assertEqual(self.storage.read('/t.txt'), text)

    def test_missing_file_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            self.storage.read('/missing')
        with self.assertRaises(FileNotFoundError):
            self.storage.delete('/missing')

    def test_append_creates_then_extends(self):
        self.storage.append('/log.txt', 'a\n')
        self.storage.append('/log.txt', 'b\n')
        self.assertEqual(self.storage.read('/log.txt'), 'a\nb\n')

    def test_list_files_sorted_and_by_folder(self):
        for path in ('/b.txt', '/a/x.txt', '/a/y.txt', '/ab.txt'):
            self.storage.write(path, '')
        self.assertEqual(self.storage.list_files(), ['/a/x.txt', '/a/y.txt', '/ab.txt', '/b.txt'])
        self.assertEqual(self.storage.list_files('/a'), ['/a/x.txt', '/a/y.txt'])
        self.assertEqual(self.storage.list_files('a/'), ['/a/x.txt', '/a/y.txt'])
        self.assertEqual(self.storage.list_files('/nothing'), [])

    def test_exists_and_delete(self):
        self.storage.write('/a', 'x')
        self.assertTrue(self.storage.exists('/a'))
        self.storage.delete('/a')
        self.assertFalse(self.storage.exists('/a'))

    def test_a_path_cannot_be_both_file_and_folder(self):
        self.storage.write('/a', 'file')
        with self.assertRaises(ValueError):
            self.storage.write('/a/b', 'x')
        self.storage.write('/c/d', 'file')
        with self.assertRaises(ValueError):
            self.storage.write('/c', 'x')

    def test_snapshot_restore_replaces_everything(self):
        self.storage.write('/keep', 'one')
        saved = self.storage.snapshot()
        self.storage.write('/keep', 'two')
        self.storage.write('/extra', 'x')
        self.storage.restore(saved)
        self.assertEqual(self.storage.list_files(), ['/keep'])
        self.assertEqual(self.storage.read('/keep'), 'one')

    def test_restore_can_swap_a_file_for_a_folder(self):
        self.storage.write('/a/b.txt', 'inside')
        saved = self.storage.snapshot()
        self.storage.delete('/a/b.txt')
        self.storage.write('/a', 'now a file')
        self.storage.restore(saved)
        self.assertEqual(self.storage.snapshot(), {'/a/b.txt': 'inside'})
        flat = {'/a': 'file'}
        self.storage.restore(flat)
        self.assertEqual(self.storage.snapshot(), flat)

    def test_snapshot_excludes_and_restore_keeps_protected_folders(self):
        self.storage.write('/logs/k.log', 'one\n')
        self.storage.write('/work/a.txt', 'a')
        saved = self.storage.snapshot(exclude=('/logs',))
        self.assertEqual(saved, {'/work/a.txt': 'a'})
        self.storage.append('/logs/k.log', 'two\n')
        self.storage.write('/work/a.txt', 'changed')
        self.storage.write('/work/b.txt', 'new')
        self.storage.restore(saved, keep=('/logs',))
        self.assertEqual(self.storage.read('/logs/k.log'), 'one\ntwo\n')
        self.assertEqual(self.storage.list_files('/work'), ['/work/a.txt'])
        self.assertEqual(self.storage.read('/work/a.txt'), 'a')

    def test_protected_paths_in_a_snapshot_are_ignored_on_restore(self):
        self.storage.write('/logs/k.log', 'real\n')
        self.storage.restore({'/logs/k.log': 'forged\n', '/a': 'x'}, keep=('/logs',))
        self.assertEqual(self.storage.read('/logs/k.log'), 'real\n')
        self.assertEqual(self.storage.read('/a'), 'x')

    def test_invalid_restore_changes_nothing(self):
        self.storage.write('/keep', 'one')
        bad_snapshots = ({'/a': 1}, {'/a': 'x', 'a': 'y'}, {'../a': 'x'}, ['/a'],
                         {'/a': 'x', '/a/b': 'y'})
        for bad in bad_snapshots:
            with self.assertRaises((TypeError, ValueError)):
                self.storage.restore(bad)
        self.assertEqual(self.storage.snapshot(), {'/keep': 'one'})

    def test_rejects_bad_paths_and_text(self):
        for bad in ('', '/', '../a', 'a/../b', 'a\\b', 'a\x00b', None):
            with self.assertRaises(ValueError):
                self.storage.write(bad, 'x')
        with self.assertRaises(TypeError):
            self.storage.write('/a', b'x')
        with self.assertRaises(TypeError):
            self.storage.append('/a', 5)

    def test_describe_counts_files(self):
        self.storage.write('/a', 'x')
        self.assertEqual(self.storage.describe()['files'], 1)


class MemoryStorageTests(StorageContract, unittest.TestCase):
    def make(self):
        return Storage(MemoryBackend())

    def test_default_backend_is_memory(self):
        self.assertEqual(Storage().describe()['kind'], 'memory')


class DiskStorageTests(StorageContract, unittest.TestCase):
    def make(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        return Storage(DiskBackend(self.folder.name))

    def test_files_land_on_disk_and_survive_a_new_storage(self):
        self.storage.write('/notes/a.txt', 'kept')
        self.assertTrue((Path(self.folder.name) / 'notes' / 'a.txt').is_file())
        again = Storage(DiskBackend(self.folder.name))
        self.assertEqual(again.read('/notes/a.txt'), 'kept')


if __name__ == '__main__':
    unittest.main()
