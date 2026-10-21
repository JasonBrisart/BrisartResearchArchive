r"""
File: brisartos/storage/tests/test_state.py

Purpose
-------
Exercise the shared state-document class (round trips, detached copies, refused
documents and failed writes) and check that the reserved path prefixes are
defined once in the schema.

Verifies: brisartos/host/serialization.py, brisartos/storage/schema.py,
brisartos/storage/state.py, brisartos/storage/storage.py.

Contains 11 test case(s) across 2 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.host.serialization (brisartos/host/serialization.py)
- brisartos.storage.schema (brisartos/storage/schema.py)
- brisartos.storage.state (brisartos/storage/state.py)
- brisartos.storage.storage (brisartos/storage/storage.py)
Standard library: unittest.
Discovered and run by run.py test (and by python -m unittest discover -s
brisartos/storage/tests); nothing imports it.

Settings / parameters
---------------------
Inputs and component instances are created in setUp or inside the individual
test methods; a Storage subclass that always fails writes stands in for a full
disk.

Edge cases
----------
Corrupt text, a document of the wrong kind, unsupported values and a failing
write are each injected on purpose.

StateFileTests:
- A missing document loads as none.
- Save then load round trips.
- The stored text carries the format and kind.
- Save returns a copy detached from the input.
- A document of another kind is refused.
- Corrupt text is refused not ignored.
- Unsupported values are refused before anything is written.
- A failed write raises and writes nothing.
- Detach copies plain data without touching storage.
- Callbacks are required.
ReservedPrefixTests:
- The reserved prefixes are defined once in the schema.

Known limitations
-----------------
- A real full disk, concurrent writers and power loss are not simulated.
- Passing proves only the 11 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
Run from the repository root.

::

    python -B -m unittest discover -s brisartos/storage/tests -p test_state.py
"""
import unittest

from brisartos.host.serialization import decode_mapping, encode_mapping
from brisartos.storage.schema import DATA_FORMAT, LOG_PREFIX, MODULES_PREFIX, PROTECTED_PREFIXES, SYSTEM_PREFIX
from brisartos.storage.state import StateFile
from brisartos.storage.storage import Storage

PATH = '/system/demo.txt'


class FullStorage(Storage):
    def write(self, path, text):
        raise OSError('disk full')


class StateFileTests(unittest.TestCase):
    def setUp(self):
        self.storage = Storage()
        self.state = StateFile(self.storage, PATH, 'demo', encode_mapping, decode_mapping)

    def test_a_missing_document_loads_as_none(self):
        self.assertIsNone(self.state.load())
        self.assertFalse(self.state.exists())

    def test_save_then_load_round_trips(self):
        self.assertEqual(self.state.save({'a': [1, True]}), {'a': [1, True]})
        self.assertTrue(self.state.exists())
        self.assertEqual(self.state.load(), {'a': [1, True]})

    def test_the_stored_text_carries_the_format_and_kind(self):
        self.state.save({'a': 1})
        self.assertEqual(decode_mapping(self.storage.read(PATH)),
                         {'format': DATA_FORMAT, 'kind': 'demo', 'payload': {'a': 1}})

    def test_save_returns_a_copy_detached_from_the_input(self):
        value = {'a': [1]}
        saved = self.state.save(value)
        value['a'].append(2)
        saved['a'].append(3)
        self.assertEqual(self.state.load(), {'a': [1]})

    def test_a_document_of_another_kind_is_refused(self):
        self.state.save({'a': 1})
        other = StateFile(self.storage, PATH, 'other', encode_mapping, decode_mapping)
        with self.assertRaises(ValueError):
            other.load()

    def test_corrupt_text_is_refused_not_ignored(self):
        self.storage.write(PATH, '{broken')
        with self.assertRaises(ValueError):
            self.state.load()

    def test_unsupported_values_are_refused_before_anything_is_written(self):
        with self.assertRaises(TypeError):
            self.state.save({'a': object()})
        self.assertFalse(self.state.exists())

    def test_a_failed_write_raises_and_writes_nothing(self):
        broken = StateFile(FullStorage(), PATH, 'demo', encode_mapping, decode_mapping)
        with self.assertRaises(OSError):
            broken.save({'a': 1})
        self.assertFalse(broken.exists())

    def test_detach_copies_plain_data_without_touching_storage(self):
        value = {'a': [1]}
        copy = self.state.detach(value)
        copy['a'].append(2)
        self.assertEqual(value, {'a': [1]})
        self.assertFalse(self.state.exists())

    def test_callbacks_are_required(self):
        for pair in ((None, None), (encode_mapping, None), (None, decode_mapping), ('x', 'y')):
            with self.assertRaises(ValueError):
                StateFile(self.storage, PATH, 'demo', *pair)


class ReservedPrefixTests(unittest.TestCase):
    def test_the_reserved_prefixes_are_defined_once_in_the_schema(self):
        self.assertEqual((LOG_PREFIX, SYSTEM_PREFIX, MODULES_PREFIX), ('/logs', '/system', '/modules'))
        self.assertEqual(PROTECTED_PREFIXES, (LOG_PREFIX, SYSTEM_PREFIX))


if __name__ == '__main__':
    unittest.main()
