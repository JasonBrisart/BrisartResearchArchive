r"""
File: brisartos/host/tests/test_system.py

Purpose
-------
Check timestamp shape, sampled hexadecimal identifier uniqueness and the type
of command-line argument results.

Verifies: brisartos/host/system.py.

Contains 3 test case(s) across 1 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.host.system (brisartos/host/system.py)
Standard library: datetime, unittest.
Discovered and run by run.py test (and by python -m unittest discover -s
brisartos/host/tests); nothing imports it.

Settings / parameters
---------------------
No module-level configuration is defined.

Inputs and component instances are created inside the individual test methods;
this file defines no shared setUp or tearDown method.

Edge cases
----------
Uniqueness is sampled over 200 identifiers, which is evidence of randomness,
not proof of its quality.

SystemTests:
- Now utc is an iso timestamp in utc.
- New id is 32 hex characters and not repeated.
- Command line arguments is a list of text.

Known limitations
-----------------
- A wrong or jumping host clock cannot be simulated here.
- Passing proves only the 3 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
Run from the repository root.

::

    python -B -m unittest discover -s brisartos/host/tests -p test_system.py
"""

import unittest
from datetime import datetime

from brisartos.host import system


class SystemTests(unittest.TestCase):
    def test_now_utc_is_an_iso_timestamp_in_utc(self):
        stamp = system.now_utc()
        self.assertTrue(stamp.endswith('+00:00'))
        self.assertIsNotNone(datetime.fromisoformat(stamp).tzinfo)

    def test_new_id_is_32_hex_characters_and_not_repeated(self):
        ids = {system.new_id() for _ in range(200)}
        self.assertEqual(len(ids), 200)
        for value in ids:
            self.assertEqual(len(value), 32)
            int(value, 16)

    def test_command_line_arguments_is_a_list_of_text(self):
        arguments = system.command_line_arguments()
        self.assertIsInstance(arguments, list)
        self.assertTrue(all(isinstance(item, str) for item in arguments))


if __name__ == '__main__':
    unittest.main()
