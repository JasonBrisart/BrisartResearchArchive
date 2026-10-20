r"""
File: brisartos/kernel/scheduler.py

Purpose
-------
Advance queued iterators in cooperative round-robin order while retaining task
states, yielded values, completion results and failure messages.

Public interface:
- class Scheduler -- A queue of cooperative tasks and their records.
- Scheduler.spawn(name, iterator) -- Queue an iterator as a named task and
  return its integer id.
- Scheduler.step() -- Advance the next waiting task by one next() and return
  its id, or None when nothing is waiting.
- Scheduler.run(steps=100) -- Perform up to steps steps and return how many
  were performed.
- Scheduler.cancel(task_id) -- Take one waiting task out of the queue; return
  False if it is not waiting.
- Scheduler.cancel_all() -- Cancel every waiting task and return how many there
  were.
- Scheduler.describe(task_id) -- Return one task's record without its iterator.
- Scheduler.status() -- Return every task's record keyed by id.

Design notes:

The queue uses a moving head and occasional prefix compaction. A successful
next call requeues the task; StopIteration records completion and Exception
records failure. Cancellation removes waiting identifiers but retains their
records and does not explicitly close the iterator. A step budget counts calls,
not elapsed time.

Communication / relationships
-----------------------------
Standard library: none.
Imported by:
- brisartos/kernel/kernel.py
Covered by tests: brisartos/kernel/tests/test_components.py.

Settings / parameters
---------------------
No module-level settings. run(steps=100) is the only tunable.

Edge cases
----------
An empty task name raises ValueError, a non-iterator raises TypeError, a
negative or non-integer step count raises ValueError, and an unknown task id
raises KeyError.

- Scheduler.spawn() raises ValueError: "task name required"
- Scheduler.spawn() raises TypeError: "task must be an iterator"
- Scheduler.run() raises ValueError: "steps must be a nonnegative integer"
- Scheduler.step() catches StopIteration -- A finished generator is recorded as
  finished and its return value kept as the result.
- Scheduler.step() catches Exception -- A task that raises is recorded as
  failed with the error text so one broken task cannot stop the others.

Known limitations
-----------------
- Cooperative only: a task that never yields blocks the whole process and
  cannot be interrupted, because Python offers no safe way to stop a running
  generator from the same thread.
- There are no priorities, preemption or timeouts, and the step count limits
  how often next() is called, not how long one call takes.
- Finished, failed and cancelled task records are kept for the life of the
  scheduler.

Examples
--------
Run from the repository root.

::

    from brisartos.kernel.scheduler import Scheduler

    scheduler = Scheduler()
    task = scheduler.spawn('demo', iter([1, 2]))
    assert scheduler.run() == 3
    assert scheduler.describe(task)['state'] == 'finished'
    waiting = scheduler.spawn('later', iter([1]))
    assert scheduler.cancel_all() == 1
"""

class Scheduler:
    def __init__(self):
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
        except Exception as error:
            task['state'] = 'failed'
            task['error'] = str(error)
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
        return True

    def cancel_all(self):
        waiting = self._pending()
        self._queue = []
        self._head = 0
        for task_id in waiting:
            self._tasks[task_id]['state'] = 'cancelled'
        return len(waiting)

    def describe(self, task_id):
        return {key: value for key, value in self._tasks[task_id].items() if key != 'iterator'}

    def status(self):
        return {task_id: self.describe(task_id) for task_id in self._tasks}
