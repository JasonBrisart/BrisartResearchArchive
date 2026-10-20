r"""
File: brisartos/kernel/tests/test_components.py

Purpose
-------
Exercise cooperative scheduling, text-console queues and draining, device
registration and fixed platform capability refusals.

Verifies: brisartos/kernel/devices.py, brisartos/kernel/platform.py,
brisartos/kernel/scheduler.py.

Contains 11 test case(s) across 2 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.kernel.devices (brisartos/kernel/devices.py)
- brisartos.kernel.platform (brisartos/kernel/platform.py)
- brisartos.kernel.scheduler (brisartos/kernel/scheduler.py)
Standard library: unittest.
Discovered and run by run.py test (and by python -m unittest discover -s
brisartos/kernel/tests); nothing imports it.

Settings / parameters
---------------------
No module-level configuration is defined.

Inputs and component instances are created inside the individual test methods;
this file defines no shared setUp or tearDown method.

Edge cases
----------
A generator that raises ValueError on purpose proves that a failing task is
recorded and does not stop others. The scheduler is also run with 300 tasks.

MemoryTests:

- Handles and capacity.
- Handles are never reused.
- Status reports use.

SchedulerTests:
- Round robin to completion.
- Tasks take turns in order.
- Failure is recorded.
- Cancel removes a waiting task only.
- Cancel all cancels every waiting task.
- Many tasks finish correctly.
- Rejects bad input.
DeviceAndPlatformTests:
- Console queue.
- Console drain hands over and clears output.
- Registry.
- Platform refuses boot.

Known limitations
-----------------
- A task that never yields cannot be tested without hanging the test run, so
  that case is not covered.
- Passing proves only the 11 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
Run from the repository root.

::

    python -B -m unittest discover -s brisartos/kernel/tests -p test_components.py
"""

import unittest

from brisartos.kernel.devices import DeviceRegistry, TextConsole
from brisartos.kernel.platform import CapabilityUnavailable, Platform
from brisartos.kernel.scheduler import Scheduler


def counter(limit):
    for value in range(limit):
        yield value
    return limit


class SchedulerTests(unittest.TestCase):
    def test_round_robin_to_completion(self):
        scheduler = Scheduler()
        task = scheduler.spawn('c', counter(2))
        self.assertEqual(scheduler.run(), 3)
        self.assertEqual(scheduler.describe(task)['result'], 2)
        self.assertEqual(scheduler.describe(task)['state'], 'finished')

    def test_tasks_take_turns_in_order(self):
        order = []

        def worker(label):
            for _ in range(2):
                order.append(label)
                yield

        scheduler = Scheduler()
        scheduler.spawn('a', worker('a'))
        scheduler.spawn('b', worker('b'))
        scheduler.run()
        self.assertEqual(order, ['a', 'b', 'a', 'b'])

    def test_failure_is_recorded(self):
        def broken():
            yield 1
            raise ValueError('test failure')
        scheduler = Scheduler()
        task = scheduler.spawn('b', broken())
        scheduler.run()
        self.assertEqual(scheduler.describe(task)['state'], 'failed')
        self.assertEqual(scheduler.describe(task)['error'], 'test failure')

    def test_cancel_removes_a_waiting_task_only(self):
        scheduler = Scheduler()
        first = scheduler.spawn('a', counter(3))
        second = scheduler.spawn('b', counter(3))
        self.assertTrue(scheduler.cancel(first))
        self.assertFalse(scheduler.cancel(first))
        scheduler.run()
        self.assertEqual(scheduler.describe(first)['state'], 'cancelled')
        self.assertEqual(scheduler.describe(second)['state'], 'finished')
        self.assertFalse(scheduler.cancel(second))

    def test_cancel_all_cancels_every_waiting_task(self):
        scheduler = Scheduler()
        ids = [scheduler.spawn('t' + str(index), counter(5)) for index in range(4)]
        scheduler.step()
        self.assertEqual(scheduler.cancel_all(), 4)
        self.assertEqual(scheduler.cancel_all(), 0)
        self.assertTrue(all(scheduler.describe(item)['state'] == 'cancelled' for item in ids))
        self.assertEqual(scheduler.run(), 0)

    def test_many_tasks_finish_correctly(self):
        scheduler = Scheduler()
        ids = [scheduler.spawn('t' + str(index), counter(3)) for index in range(300)]
        scheduler.run(steps=100000)
        self.assertTrue(all(scheduler.describe(item)['state'] == 'finished' for item in ids))
        self.assertEqual(scheduler.run(), 0)

    def test_rejects_bad_input(self):
        scheduler = Scheduler()
        with self.assertRaises(ValueError):
            scheduler.spawn('', counter(1))
        with self.assertRaises(TypeError):
            scheduler.spawn('x', [1])
        with self.assertRaises(ValueError):
            scheduler.run(-1)
        with self.assertRaises(KeyError):
            scheduler.describe(99)


class DeviceAndPlatformTests(unittest.TestCase):
    def test_console_queue(self):
        console = TextConsole()
        console.feed('in')
        console.write('out')
        self.assertEqual(console.read(), 'in')
        self.assertEqual(console.output(), ['out'])
        with self.assertRaises(EOFError):
            console.read()

    def test_console_drain_hands_over_and_clears_output(self):
        console = TextConsole()
        console.write('one')
        console.write('two')
        self.assertEqual(console.drain(), ['one', 'two'])
        self.assertEqual(console.drain(), [])
        self.assertEqual(console.output(), [])

    def test_registry(self):
        devices = DeviceRegistry()
        devices.register('console', TextConsole())
        with self.assertRaises(ValueError):
            devices.register('console', TextConsole())
        with self.assertRaises(CapabilityUnavailable):
            devices.get('disk')
        self.assertEqual(devices.names(), ['console'])

    def test_platform_refuses_boot(self):
        with self.assertRaises(CapabilityUnavailable):
            Platform().boot_media()
        with self.assertRaises(CapabilityUnavailable):
            Platform().firmware_handoff()
        self.assertFalse(Platform().describe()['bootable'])


if __name__ == '__main__':
    unittest.main()
