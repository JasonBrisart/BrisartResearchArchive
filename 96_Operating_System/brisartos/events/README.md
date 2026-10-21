# Structured Event Recording

`events.py` records numbered runtime outcomes through supplied storage and clock objects, with a bounded recent-event list.

## Record contract

`EventLog(storage, clock, limit=1000)` requires a positive integer limit. `record(source, message, kind="message", details=None)` validates the source and plain-data details, obtains a timestamp and appends the text log line before publishing the sequence number and recent entry.

Entries contain `sequence`, `time`, `source`, `kind`, `message` and `details`. `recent(count=None)` returns detached entries oldest first. Mutating supplied details or returned entries does not alter retained details. `total` counts successfully appended events for this instance.

Core kinds are `kernel.started`, `kernel.stopped`, `module.loaded`, `module.rejected`, `module.started`, `module.finished`, `module.failed`, `service.started`, `service.stopped`, `task.spawned`, `task.finished` and `task.failed`. Custom messages default to `message`.

## Persistence and failure semantics

Text lines retain `TIME SOURCE: MESSAGE` in `/logs/SOURCE.log`. Kind/details remain in memory; they are not recoverable as structured records from these text logs. A new instance restarts sequence numbering. Files are unbounded and are not rotated. The `/logs` prefix is `LOG_PREFIX` in `storage/schema.py`, not a constant defined here.

An append exception leaves the in-memory total and recent list unchanged, although the backend may have partially written the line before raising. This is not an atomic transaction between memory and disk, a power-loss guarantee or a thread-safe recorder. Messages are written as supplied, including newlines. Details have no cycle detection or total-size budget.

## Tests

`tests/test_events.py` checks numbering, limits, copies and source validation. Append-failure ordering and nested detail copies are checked in `../kernel/tests/test_architecture.py`.
