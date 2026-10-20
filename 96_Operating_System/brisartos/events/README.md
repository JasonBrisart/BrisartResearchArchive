# Event Log

`events.py` defines `EventLog`, the one recorder every BrisartOS event goes through.

The kernel records its start, stop and module-load failures here, and the module system records each module's start, finish, failure and its own `log` calls here. Neither writes log files directly.

## `EventLog(storage, clock, limit=1000)`

The log is given its storage and its clock rather than importing them. The kernel passes its storage and the host UTC clock; a test can pass memory storage and a function that always returns the same text. `limit` must be a positive integer.

`record(source, message)` checks that `source` is a safe name, numbers the event, keeps it in the recent list and appends one line to `/logs/SOURCE.log`:

```text
2026-10-20T19:00:00+00:00 kernel: stopped
```

`recent(count=None)` returns copies of the newest events, oldest first, each with `sequence`, `time`, `source` and `message`. `total` counts every event ever recorded, including the ones the recent list has dropped.

```python
from brisartos.events.events import EventLog
from brisartos.storage.storage import Storage

store = Storage()
events = EventLog(store, lambda: "T", limit=2)
events.record("kernel", "started")
events.record("demo", "hello")
events.record("kernel", "stopped")
assert [event["sequence"] for event in events.recent()] == [2, 3]
assert events.total == 3
assert store.read("/logs/kernel.log") == "T kernel: started\nT kernel: stopped\n"
```

## What it does not do

Only the recent list is bounded. Log files grow until something deletes them, and nothing rotates them. The recent list and `total` are in memory, so a new log over the same storage starts numbering from 1 again while the files keep their old lines.

The memory entry is added before the file line, so if the append fails the entry exists without its line. A message containing a newline is written as given and spans several lines.

## Tests

`tests/test_events.py` uses memory storage and a fixed clock to check numbering, the bounded list, per-source files, copies returned by `recent`, refused sources and refused limits.
