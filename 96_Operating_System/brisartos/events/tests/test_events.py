r"""
File: brisartos/events/tests/test_events.py

Purpose
-------
Exercise event numbering, the bounded recent list, per-source log files, source
validation and the copies returned by recent, using a fixed clock and memory
storage instead of a kernel.

Verifies: brisartos/events/events.py, brisartos/storage/storage.py.

Contains 7 test case(s) across 1 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.events.events (brisartos/events/events.py)
- brisartos.storage.storage (brisartos/storage/storage.py)
Standard library: unittest.
Discovered and run by run.py test (and by python -m unittest discover -s
brisartos/events/tests); nothing imports it.

Settings / parameters
---------------------
Fixture helpers in this file: EventLogTests: setUp.

Edge cases
----------
The clock is a fixed function, so every line in a log file is predictable.

EventLogTests:
- Record numbers keeps and writes an event.
- Each source gets its own file.
- Recent is capped but the total and files are not.
- Recent count returns the newest.
- Recent returns copies.
- Unsafe sources record nothing.
- Limit must be a positive integer.

Known limitations
-----------------
- A storage failure in the middle of record is not simulated.
- Passing proves only the 7 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
Run from the repository root.

::

    python -B -m unittest discover -s brisartos/events/tests -p test_events.py
"""

import unittest

from brisartos.events.events import EventLog
from brisartos.storage.storage import Storage


class EventLogTests(unittest.TestCase):
    def setUp(self):
        self.storage = Storage()
        self.events = EventLog(self.storage, lambda: '2026-01-01T00:00:00+00:00', limit=3)

    def test_record_numbers_keeps_and_writes_an_event(self):
        self.events.record('probe', 'hello')
        self.assertEqual(self.events.recent(), [{'sequence': 1, 'time': '2026-01-01T00:00:00+00:00',
                                                 'source': 'probe', 'message': 'hello'}])
        self.assertEqual(self.storage.read('/logs/probe.log'), '2026-01-01T00:00:00+00:00 probe: hello\n')

    def test_each_source_gets_its_own_file(self):
        self.events.record('one', 'a')
        self.events.record('two', 'b')
        self.assertEqual(self.storage.list_files('/logs'), ['/logs/one.log', '/logs/two.log'])

    def test_recent_is_capped_but_the_total_and_files_are_not(self):
        for index in range(10):
            self.events.record('probe', 'event ' + str(index))
        self.assertEqual([event['sequence'] for event in self.events.recent()], [8, 9, 10])
        self.assertEqual(self.events.total, 10)
        self.assertEqual(len(self.storage.read('/logs/probe.log').splitlines()), 10)

    def test_recent_count_returns_the_newest(self):
        for index in range(3):
            self.events.record('probe', str(index))
        self.assertEqual([event['message'] for event in self.events.recent(2)], ['1', '2'])
        for bad in (0, -1, 1.5, True):
            with self.assertRaises(ValueError):
                self.events.recent(bad)

    def test_recent_returns_copies(self):
        self.events.record('probe', 'kept')
        self.events.recent()[0]['message'] = 'changed'
        self.assertEqual(self.events.recent()[0]['message'], 'kept')

    def test_unsafe_sources_record_nothing(self):
        for bad in ('../x', 'a/b', '', 'a b', None):
            with self.assertRaises(ValueError):
                self.events.record(bad, 'x')
        self.assertEqual(self.events.total, 0)
        self.assertEqual(self.storage.list_files(), [])

    def test_limit_must_be_a_positive_integer(self):
        for bad in (0, -1, 1.5, None, True):
            with self.assertRaises(ValueError):
                EventLog(self.storage, lambda: 'T', bad)


if __name__ == '__main__':
    unittest.main()
