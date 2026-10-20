r"""
File: brisartos/host/tests/test_disk.py

Purpose
-------
Exercise DiskBackend file round trips, temporary-file filtering, append, prefix
listings, deletion, path conflicts and root-escape rejection.

Verifies: brisartos/host/disk.py.

Contains 12 test case(s) across 1 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.host.disk (brisartos/host/disk.py)
Standard library: pathlib, tempfile, unittest.
Discovered and run by run.py test (and by python -m unittest discover -s
brisartos/host/tests); nothing imports it.

Settings / parameters
---------------------
No module-level configuration is defined.

Fixture helpers in this file: DiskBackendTests: setUp.

Edge cases
----------
The symlink test is skipped (not failed) where the operating system or account
cannot create symlinks, where the account lacks symlink privileges. Text round
trips use CRLF, a bare CR and non-ASCII characters.

DiskBackendTests:
- Root is created and described.
- Text round trips exactly.
- Write leaves no temporary file.
- Listing ignores interrupted temporary files.
- Append creates then extends.
- Paths by prefix only walks that folder.
- Delete removes the file and empty folders.
- Delete keeps folders that still hold files.
- Missing file raises file not found.
- A path cannot be both file and folder.
- Paths that leave the root are refused.
- Symlink that leaves the root is refused.

Known limitations
-----------------
- A crash in the middle of a write, a full disk and two processes sharing one
  folder are not simulated.
- Passing proves only the 12 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
Run from the repository root.

::

    python -B -m unittest discover -s brisartos/host/tests -p test_disk.py
"""

import tempfile
import unittest
from pathlib import Path

from brisartos.host.disk import TEMP_SUFFIX, DiskBackend


class DiskBackendTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.disk = DiskBackend(self.root / 'data')

    def test_root_is_created_and_described(self):
        self.assertTrue((self.root / 'data').is_dir())
        self.assertEqual(self.disk.describe()['kind'], 'disk')

    def test_text_round_trips_exactly(self):
        text = 'line one\r\nline two\rline three\n\u00e9\u4e2d\n'
        self.disk.write('/notes/a.txt', text)
        self.assertEqual(self.disk.read('/notes/a.txt'), text)
        self.assertEqual((self.root / 'data' / 'notes' / 'a.txt').read_bytes(), text.encode('utf-8'))

    def test_write_leaves_no_temporary_file(self):
        self.disk.write('/a.txt', 'one')
        self.disk.write('/a.txt', 'two')
        names = sorted(item.name for item in (self.root / 'data').iterdir())
        self.assertEqual(names, ['a.txt'])

    def test_listing_ignores_interrupted_temporary_files(self):
        self.disk.write('/a.txt', 'one')
        (self.root / 'data' / ('b.txt' + TEMP_SUFFIX)).write_text('half written')
        self.assertEqual(self.disk.paths(), ['/a.txt'])

    def test_append_creates_then_extends(self):
        self.disk.append('/log/x.log', 'a\n')
        self.disk.append('/log/x.log', 'b\n')
        self.assertEqual(self.disk.read('/log/x.log'), 'a\nb\n')

    def test_paths_by_prefix_only_walks_that_folder(self):
        for path in ('/a/x.txt', '/a/deep/y.txt', '/ab.txt', '/b/z.txt'):
            self.disk.write(path, '')
        self.assertEqual(self.disk.paths('/a'), ['/a/deep/y.txt', '/a/x.txt'])
        self.assertEqual(self.disk.paths('/missing'), [])
        self.assertEqual(len(self.disk.paths()), 4)

    def test_delete_removes_the_file_and_empty_folders(self):
        self.disk.write('/a/b/c.txt', 'x')
        self.disk.delete('/a/b/c.txt')
        self.assertFalse((self.root / 'data' / 'a').exists())
        with self.assertRaises(FileNotFoundError):
            self.disk.delete('/a/b/c.txt')

    def test_delete_keeps_folders_that_still_hold_files(self):
        self.disk.write('/a/b.txt', 'x')
        self.disk.write('/a/c.txt', 'y')
        self.disk.delete('/a/b.txt')
        self.assertEqual(self.disk.paths(), ['/a/c.txt'])

    def test_missing_file_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            self.disk.read('/missing')
        self.assertFalse(self.disk.exists('/missing'))

    def test_a_path_cannot_be_both_file_and_folder(self):
        self.disk.write('/a', 'file')
        with self.assertRaises(ValueError):
            self.disk.write('/a/b', 'x')
        self.disk.write('/c/d', 'file')
        with self.assertRaises(ValueError):
            self.disk.write('/c', 'x')
        with self.assertRaises(ValueError):
            self.disk.append('/c', 'x')

    def test_paths_that_leave_the_root_are_refused(self):
        for bad in ('/../outside.txt', '/a/../../outside.txt'):
            with self.assertRaises(ValueError):
                self.disk.write(bad, 'x')
        self.assertFalse((self.root / 'outside.txt').exists())

    def test_symlink_that_leaves_the_root_is_refused(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        try:
            (self.root / 'data' / 'link').symlink_to(outside.name, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('symlinks unavailable')
        with self.assertRaises(ValueError):
            self.disk.write('/link/escape.txt', 'x')
        with self.assertRaises(ValueError):
            self.disk.read('/link/escape.txt')


if __name__ == '__main__':
    unittest.main()
