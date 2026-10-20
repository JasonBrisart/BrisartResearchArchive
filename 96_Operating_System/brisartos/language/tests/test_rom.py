r"""
File: brisartos/language/tests/test_rom.py

Purpose
-------
Exercise source-ROM lifecycle transitions, copied snapshots, source and step
limits, fault capture and independence between instances.

Verifies: brisartos/language/lexer.py, brisartos/language/rom.py.

Contains 19 test case(s) across 1 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.language.lexer (brisartos/language/lexer.py)
- brisartos.language.rom (brisartos/language/rom.py)
Standard library: unittest.
Discovered and run by run.py test (and by python -m unittest discover -s
brisartos/language/tests); nothing imports it.

Settings / parameters
---------------------
No module-level configuration is defined.

Inputs and component instances are created inside the individual test methods;
this file defines no shared setUp or tearDown method.

Edge cases
----------
Fault tests rely on the interpreter raising real errors, such as
ZeroDivisionError and an undefined name.

SourceROMTests:
- Default boot.
- Truthful capabilities.
- Initial reset.
- Repeat requires reset.
- Reset reboots cleanly.
- Snapshot isolation.
- Source readonly property.
- Rom type.
- Source limit.
- Invalid source limits.
- Invalid step limits.
- Reject unsupported python.
- Fault recorded.
- Partial output preserved.
- Budget stops loop.
- Reset clears fault.
- Empty rom.
- Loop and branch.
- Instances independent.

Known limitations
-----------------
- A lifecycle model is tested, not firmware.
- Passing proves only the 19 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
Run from the repository root.

::

    python -B -m unittest discover -s brisartos/language/tests -p test_rom.py
"""

import unittest

from brisartos.language.rom import SourceROMMachine
from brisartos.language.lexer import LanguageError


class SourceROMTests(unittest.TestCase):
    def test_default_boot(self):
        r=SourceROMMachine().boot()
        self.assertEqual(r['state'],'halted')
        self.assertTrue(r['variables']['ready'])
        self.assertEqual(r['output'],['BrisartOS source-ROM model'])

    def test_truthful_capabilities(self):
        r=SourceROMMachine().boot()
        for key in ('hardware_boot','full_python','self_hosting'):
            self.assertIs(r[key],False)

    def test_initial_reset(self):
        self.assertEqual(SourceROMMachine().snapshot()['state'],'reset')

    def test_repeat_requires_reset(self):
        m=SourceROMMachine();m.boot()
        with self.assertRaises(RuntimeError):m.boot()

    def test_reset_reboots_cleanly(self):
        m=SourceROMMachine('x = 1\nprint(x)');a=m.boot();m.reset();b=m.boot()
        self.assertEqual(a['output'],b['output']);self.assertEqual(b['boot_attempts'],2)

    def test_snapshot_isolation(self):
        m=SourceROMMachine();r=m.boot();r['variables']['ready']=False;r['output'].clear()
        self.assertTrue(m.snapshot()['variables']['ready']);self.assertTrue(m.snapshot()['output'])

    def test_source_readonly_property(self):
        m=SourceROMMachine()
        with self.assertRaises(AttributeError):m.source='pass'

    def test_rom_type(self):
        for value in (None,1,b'pass',[]):
            with self.assertRaises(TypeError):SourceROMMachine(value)

    def test_source_limit(self):
        with self.assertRaises(ValueError):SourceROMMachine('pass',max_source_chars=3)
        self.assertEqual(SourceROMMachine('pass',max_source_chars=4).boot()['state'],'halted')

    def test_invalid_source_limits(self):
        for value in (True,0,-1,1.5,None):
            with self.assertRaises(ValueError):SourceROMMachine(max_source_chars=value)

    def test_invalid_step_limits(self):
        for value in (True,0,-1,1.5,None):
            with self.assertRaises(ValueError):SourceROMMachine(max_steps=value)

    def test_reject_unsupported_python(self):
        for source in ('import os','def f():\n    pass','class C:\n    pass'):
            with self.assertRaises(LanguageError):SourceROMMachine(source)

    def test_fault_recorded(self):
        m=SourceROMMachine('print(1 // 0)')
        with self.assertRaises(ZeroDivisionError):m.boot()
        self.assertEqual(m.snapshot()['state'],'faulted')
        self.assertIn('ZeroDivisionError',m.snapshot()['fault'])

    def test_partial_output_preserved(self):
        m=SourceROMMachine('print("before")\nprint(missing)')
        with self.assertRaises(LanguageError):m.boot()
        self.assertEqual(m.snapshot()['output'],['before'])

    def test_budget_stops_loop(self):
        m=SourceROMMachine('while True:\n    pass',max_steps=20)
        with self.assertRaises(LanguageError):m.boot()
        self.assertEqual(m.snapshot()['state'],'faulted')

    def test_reset_clears_fault(self):
        m=SourceROMMachine('print(missing)')
        with self.assertRaises(LanguageError):m.boot()
        m.reset();r=m.snapshot()
        self.assertIsNone(r['fault']);self.assertEqual(r['steps'],0)
        self.assertEqual(r['variables'],{});self.assertEqual(r['output'],[])

    def test_empty_rom(self):
        self.assertEqual(SourceROMMachine('').boot()['steps'],0)

    def test_loop_and_branch(self):
        r=SourceROMMachine('x = 0\nwhile x < 3:\n    x = x + 1\nif x == 3:\n    print("ready")\nelse:\n    print("wrong")').boot()
        self.assertEqual(r['output'],['ready'])

    def test_instances_independent(self):
        a=SourceROMMachine('x = 4');b=SourceROMMachine('x = 7')
        self.assertEqual(a.boot()['variables']['x'],4)
        self.assertEqual(b.boot()['variables']['x'],7)


if __name__ == '__main__':
    unittest.main()
