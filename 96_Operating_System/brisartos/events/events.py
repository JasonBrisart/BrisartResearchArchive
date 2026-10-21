r"""
File: brisartos/events/events.py

Purpose
-------
Record structured runtime outcomes after successful text-log append and retain
a bounded recent-event list.

Public interface:
- class EventLog -- A bounded structured event recorder over supplied storage
  and clock.
- EventLog(storage, clock, limit=1000) -- Bind storage, clock and a positive
  recent-event limit.
- EventLog.record(source, message, kind='message', details=None) -- Append a
  text line, then publish a numbered structured event.
- EventLog.recent(count=None) -- Return detached recent entries, oldest first.

Design notes:

Append succeeds before sequence and recent state are published. Existing text
log lines retain their display format; structured kind/details are
instance-local and copied on input and output.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.common.names (brisartos/common/names.py)
- brisartos.storage.schema (brisartos/storage/schema.py)
Standard library: none.
Imported by:
- brisartos/kernel/composition.py
Covered by tests: brisartos/events/tests/test_events.py,
brisartos/extensions/tests/test_api.py,
brisartos/kernel/tests/test_architecture.py.

Settings / parameters
---------------------
This file defines no constants; the log folder prefix is read from
brisartos/storage/schema.py.

Edge cases
----------
Invalid inputs are rejected before the documented operation; backend and
callback failures propagate unless explicitly collected.

- _copy() raises TypeError: "event details must contain plain data"
- EventLog.__init__() raises ValueError: "event limit must be a positive
  integer"
- EventLog.record() raises ValueError: "event message and kind must be text"
- EventLog.record() raises TypeError: "event details must be a dictionary"
- EventLog.recent() raises ValueError: "count must be a positive integer"

Known limitations
-----------------
- Log files are unbounded and not fsync-durable; an append can partially write
  before raising.
- Sequence numbers restart for each instance; structured fields are not
  persisted in text logs.
- No locking, cycle detection for details or comprehensive resource budget is
  provided.

Examples
--------
Run from the repository root.

::

    from brisartos.events.events import EventLog
    from brisartos.storage.storage import Storage
    e = EventLog(Storage(), lambda: 'T')
    e.record('demo', 'ready', kind='kernel.started')
    assert e.recent()[0]['kind'] == 'kernel.started'
"""
from ..common.names import require_name
from ..storage.schema import LOG_PREFIX

def _copy(value):
    if isinstance(value, dict):
        return {key: _copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy(item) for item in value]
    if value is None or type(value) in (str, int, float, bool):
        return value
    raise TypeError('event details must contain plain data')

class EventLog:
    def __init__(self, storage, clock, limit=1000):
        if type(limit) is not int or limit < 1:
            raise ValueError('event limit must be a positive integer')
        self._storage, self._clock = storage, clock
        self.limit, self.total, self._recent = limit, 0, []
    def record(self, source, message, kind='message', details=None):
        require_name(source, 'log source')
        if not isinstance(message, str) or not isinstance(kind, str) or not kind:
            raise ValueError('event message and kind must be text')
        if details is not None and not isinstance(details, dict):
            raise TypeError('event details must be a dictionary')
        details = _copy({} if details is None else details)
        stamp = self._clock()
        entry = {'sequence': self.total + 1, 'time': stamp, 'source': source,
                 'kind': kind, 'message': message, 'details': details}
        self._storage.append(LOG_PREFIX + '/' + source + '.log', stamp + ' ' + source + ': ' + message + '\n')
        self.total += 1
        self._recent.append(entry)
        if len(self._recent) > self.limit:
            del self._recent[0]
    def recent(self, count=None):
        if count is not None and (type(count) is not int or count < 1):
            raise ValueError('count must be a positive integer')
        return _copy(self._recent if count is None else self._recent[-count:])
