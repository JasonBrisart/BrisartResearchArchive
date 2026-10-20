r"""
File: brisartos/events/events.py

Purpose
-------
Record runtime events as numbered entries in a bounded recent-event list and as
timestamped lines in one log file per source.

Public interface:
- class EventLog -- The event recorder shared by the kernel and the module
  system.
- EventLog(storage, clock, limit=1000) -- Bind the storage the log files are
  appended to, a callable returning the current time as text, and how many
  recent events to keep in memory.
- EventLog.record(source, message) -- Number an event, keep it in the recent
  list and append a line to /logs/SOURCE.log.
- EventLog.recent(count=None) -- Return copies of the newest recent events,
  oldest first; all of them when count is None.

Design notes:

EventLog receives its storage and clock instead of importing them, so it
depends only on the shared name validator and can be built in a test with a
fixed clock. The source is validated before anything changes. The in-memory
entry is added before the file line is appended, so a failed append leaves an
entry without its line. Only the recent list is bounded; the total keeps
counting every event and log files are never trimmed.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.common.names (brisartos/common/names.py)
Standard library: none.
Imported by:
- brisartos/kernel/kernel.py
Covered by tests: brisartos/events/tests/test_events.py,
brisartos/extensions/tests/test_api.py.

Settings / parameters
---------------------
- LOG_FOLDER = '/logs' -- The storage folder that holds one SOURCE.log file per
  event source.

Edge cases
----------
An unsafe source name raises ValueError before anything is recorded. Errors
raised by the clock or by storage pass through unchanged.

- EventLog.__init__() raises ValueError: "event limit must be a positive
  integer"
- EventLog.recent() raises ValueError: "count must be a positive integer"

Known limitations
-----------------
- Log files grow without limit; nothing rotates or trims them.
- The recent list and the total live in memory, so a new EventLog over the same
  storage starts again from zero.
- The message is written as given, so a message containing a newline spans
  several lines in its log file.

Examples
--------
Run from the repository root.

::

    from brisartos.events.events import EventLog
    from brisartos.storage.storage import Storage

    store = Storage()
    events = EventLog(store, lambda: 'T', limit=2)
    for word in ('one', 'two', 'three'):
        events.record('demo', word)
    assert [event['message'] for event in events.recent()] == ['two', 'three']
    assert events.total == 3
    assert store.read('/logs/demo.log') == 'T demo: one\nT demo: two\nT demo: three\n'
"""

from ..common.names import require_name

LOG_FOLDER = '/logs'


class EventLog:
    def __init__(self, storage, clock, limit=1000):
        if type(limit) is not int or limit < 1:
            raise ValueError('event limit must be a positive integer')
        self._storage = storage
        self._clock = clock
        self.limit = limit
        self.total = 0
        self._recent = []

    def record(self, source, message):
        require_name(source, 'log source')
        stamp = self._clock()
        self.total += 1
        self._recent.append({'sequence': self.total, 'time': stamp, 'source': source, 'message': message})
        if len(self._recent) > self.limit:
            del self._recent[0]
        self._storage.append(LOG_FOLDER + '/' + source + '.log', stamp + ' ' + source + ': ' + message + '\n')

    def recent(self, count=None):
        if count is None:
            return [dict(event) for event in self._recent]
        if type(count) is not int or count < 1:
            raise ValueError('count must be a positive integer')
        return [dict(event) for event in self._recent[-count:]]
