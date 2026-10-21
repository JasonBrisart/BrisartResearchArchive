r"""
File: brisartos/machine/scheduler.py

Purpose
-------
Advance cooperative iterator tasks, emit structured outcomes and close
cancelled iterators while collecting cleanup failures.

Public interface:
- class Scheduler -- Cooperative task records, queue and optional event
  integration.
- Scheduler(events=None) -- Create an empty scheduler with optional events.
- Scheduler.spawn(name, iterator) -- Queue a named iterator and return its
  identifier.
- Scheduler.step() -- Advance one pending task and record completion or
  failure.
- Scheduler.run(steps=100) -- Perform at most the requested number of iterator
  advances.
- Scheduler.cancel(task_id) -- Cancel one ready task and attempt iterator
  close.
- Scheduler.cancel_all() -- Cancel and close all waiting tasks; return their
  count.
- Scheduler.describe(task_id) -- Return one task record without its iterator.
- Scheduler.status() -- Return all public task records.

Design notes:

Round-robin stepping remains bounded by advances, not elapsed time.
Cancellation removes pending work before attempting close; logging and close
failures are retained rather than stopping other cleanup.

Communication / relationships
-----------------------------
Standard library: none.
Imported by:
- brisartos/kernel/composition.py
Covered by tests: brisartos/machine/tests/test_components.py.

Settings / parameters
---------------------
Constructor arguments select the supplied components and policies; no
module-level configuration is defined.

Edge cases
----------
Invalid inputs are rejected before the documented operation; backend and
callback failures propagate unless explicitly collected.

- Scheduler.spawn() raises ValueError: "task name required"
- Scheduler.spawn() raises TypeError: "task must be an iterator"
- Scheduler.run() raises ValueError: "steps must be a nonnegative integer"
- Scheduler.step() catches StopIteration -- Collect the failure as documented
  and continue cleanup or report it to the caller.
- Scheduler.step() catches Exception -- Collect the failure as documented and
  continue cleanup or report it to the caller.
- Scheduler._record() catches BaseException -- Collect the failure as
  documented and continue cleanup or report it to the caller.
- Scheduler._close() catches BaseException -- Collect the failure as documented
  and continue cleanup or report it to the caller.

Known limitations
-----------------
- Non-yielding iterators block the process; there is no preemption or timeout.
- Task records and cleanup errors remain instance-local and unbounded.

Examples
--------
Run from the repository root.

::

    from brisartos.machine.scheduler import Scheduler
    s = Scheduler()
    t = s.spawn('demo', iter([1]))
    s.run()
    assert s.describe(t)['state'] == 'finished'
"""
class Scheduler:
    def __init__(self, events=None):
        self._events = events
        self.cleanup_errors = []
        self._next = 1
        self._tasks = {}
        self._queue = []
        self._head = 0

    def _pending(self):
        return self._queue[self._head:]

    def _take(self):
        task_id = self._queue[self._head]
        self._head += 1
        if self._head > 64 and self._head * 2 > len(self._queue):
            del self._queue[:self._head]
            self._head = 0
        return task_id

    def spawn(self, name, iterator):
        if not isinstance(name, str) or not name:
            raise ValueError('task name required')
        if not hasattr(iterator, '__next__'):
            raise TypeError('task must be an iterator')
        task_id = self._next
        self._next += 1
        self._tasks[task_id] = {'name': name, 'state': 'ready', 'iterator': iterator,
                                'result': None, 'error': None}
        self._queue.append(task_id)
        self._record('task.spawned', task_id)
        return task_id

    def step(self):
        if self._head >= len(self._queue):
            return None
        task_id = self._take()
        task = self._tasks[task_id]
        try:
            task['result'] = next(task['iterator'])
        except StopIteration as stopped:
            task['state'] = 'finished'
            task['result'] = stopped.value
            self._record('task.finished', task_id)
        except Exception as error:
            task['state'] = 'failed'
            task['error'] = str(error)
            self._record('task.failed', task_id)
        else:
            self._queue.append(task_id)
        return task_id

    def run(self, steps=100):
        if type(steps) is not int or steps < 0:
            raise ValueError('steps must be a nonnegative integer')
        count = 0
        while self._head < len(self._queue) and count < steps:
            self.step()
            count += 1
        return count

    def cancel(self, task_id):
        task = self._tasks[task_id]
        if task['state'] != 'ready':
            return False
        del self._queue[self._queue.index(task_id, self._head)]
        task['state'] = 'cancelled'
        self._close(task_id)
        return True

    def cancel_all(self):
        waiting = self._pending()
        self._queue = []
        self._head = 0
        for task_id in waiting:
            self._tasks[task_id]['state'] = 'cancelled'
            self._close(task_id)
        return len(waiting)

    def describe(self, task_id):
        return {key: value for key, value in self._tasks[task_id].items() if key != 'iterator'}

    def status(self):
        return {task_id: self.describe(task_id) for task_id in self._tasks}
    def _record(self, kind, task_id):
        if self._events is not None:
            try:
                self._events.record('scheduler', kind, kind=kind, details={'task': task_id})
            except BaseException as error:
                self.cleanup_errors.append({'task': task_id, 'error': 'logging: ' + str(error)})
    def _close(self, task_id):
        try:
            close = getattr(self._tasks[task_id]['iterator'], 'close', None)
            if close is not None:
                close()
        except BaseException as error:
            self.cleanup_errors.append({'task': task_id, 'error': type(error).__name__ + ': ' + str(error)})
