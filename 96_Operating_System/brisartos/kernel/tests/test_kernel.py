r"""
File: brisartos/kernel/tests/test_kernel.py

Purpose
-------
Exercise kernel lifecycle, service registration, event retention, log-source
validation, stored-program execution and disk-backed file persistence.

Verifies: brisartos/kernel/kernel.py, brisartos/modules/api.py.

Contains 11 test case(s) across 1 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.kernel.kernel (brisartos/kernel/kernel.py)
- brisartos.modules.api (brisartos/modules/api.py)
Standard library: tempfile, unittest.
Discovered and run by run.py test (and by python -m unittest discover -s
brisartos/kernel/tests); nothing imports it.

Settings / parameters
---------------------
No module-level configuration is defined.

Fixture helpers in this file: KernelTests: setUp, tearDown.

Edge cases
----------
An invalid event limit, an unsafe log source and a second start or stop must
each raise. Disk tests use temporary folders.

KernelTests:
- Lifecycle.
- Builtin services.
- Log records event and file.
- Log source must be a safe name.
- Events are capped but numbering continues.
- Event limit must be positive.
- Run file.
- Stop cancels ready tasks.
- Describe is honest.
- Disk kernel persists between kernels.
- Missing modules folder is fine.

Known limitations
-----------------
- One process and one thread; module behavior is tested in
  brisartos/modules/tests/.
- Passing proves only the 11 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
Run from the repository root.

::

    python -B -m unittest discover -s brisartos/kernel/tests -p test_kernel.py
"""

import tempfile
import unittest

from brisartos.kernel.kernel import Kernel
from brisartos.modules.api import MODULE_ABI


def counter(limit):
    for value in range(limit):
        yield value
    return limit


class KernelTests(unittest.TestCase):
    def setUp(self):
        self.kernel = Kernel()
        self.kernel.start()

    def tearDown(self):
        if self.kernel.state == 'running':
            self.kernel.stop()

    def test_lifecycle(self):
        self.assertEqual(self.kernel.state, 'running')
        with self.assertRaises(RuntimeError):
            self.kernel.start()
        self.kernel.stop()
        self.assertEqual(self.kernel.state, 'stopped')
        with self.assertRaises(RuntimeError):
            self.kernel.stop()

    def test_builtin_services(self):
        self.assertEqual(self.kernel.services.names(), ['archive', 'settings', 'updates'])

    def test_log_records_event_and_file(self):
        self.kernel.log('probe', 'hello')
        self.assertEqual(self.kernel.events[-1]['message'], 'hello')
        self.assertIn('probe: hello', self.kernel.storage.read('/logs/probe.log'))

    def test_log_source_must_be_a_safe_name(self):
        for bad in ('../x', 'a/b', '', 'a b'):
            with self.assertRaises(ValueError):
                self.kernel.log(bad, 'x')

    def test_events_are_capped_but_numbering_continues(self):
        small = Kernel(event_limit=3)
        small.start()
        for index in range(10):
            small.log('probe', 'event ' + str(index))
        self.assertEqual(len(small.events), 3)
        sequences = [event['sequence'] for event in small.events]
        self.assertEqual(sequences, [9, 10, 11])
        self.assertEqual(small.describe()['events'], 11)
        self.assertEqual(len(small.storage.read('/logs/probe.log').splitlines()), 10)

    def test_event_limit_must_be_positive(self):
        for bad in (0, -1, 1.5, None, True):
            with self.assertRaises(ValueError):
                Kernel(event_limit=bad)

    def test_run_file(self):
        self.kernel.storage.write('/p.py', 'x = 2\nprint(x * 3)')
        self.assertEqual(self.kernel.run_file('/p.py')['output'], ['6'])

    def test_stop_cancels_ready_tasks(self):
        task = self.kernel.scheduler.spawn('c', counter(5))
        self.kernel.stop()
        self.assertEqual(self.kernel.scheduler.describe(task)['state'], 'cancelled')

    def test_describe_is_honest(self):
        info = self.kernel.describe()
        self.assertFalse(info['platform']['bootable'])
        self.assertEqual(info['storage']['kind'], 'memory')
        self.assertEqual(info['module_abi'], MODULE_ABI)

    def test_disk_kernel_persists_between_kernels(self):
        with tempfile.TemporaryDirectory() as folder:
            first = Kernel(data_root=folder)
            first.start()
            first.storage.write('/notes.txt', 'kept')
            first.stop()
            second = Kernel(data_root=folder)
            second.start()
            self.assertEqual(second.storage.read('/notes.txt'), 'kept')
            self.assertIn('stopped', second.storage.read('/logs/kernel.log'))
            second.stop()

    def test_missing_modules_folder_is_fine(self):
        with tempfile.TemporaryDirectory() as folder:
            kernel = Kernel(modules_path=folder + '/none')
            kernel.start()
            self.assertEqual(kernel.modules.names(), [])
            kernel.stop()


if __name__ == '__main__':
    unittest.main()
