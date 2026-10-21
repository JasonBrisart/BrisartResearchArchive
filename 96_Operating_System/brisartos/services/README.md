# Stateful Services and Lifecycle Registry

This directory implements ordered service lifecycle and three write-through state services: settings, archive snapshots and update candidates.

## `registry.py`

`ServiceRecord` holds name, live object, persistence declaration and lifecycle state. `ServiceRegistry.register()` validates names and rejects duplicates and None objects. `get()` remains a trusted-runtime live-object accessor. `describe()` returns name, version, status, class, state and persistent.

`start_all()` invokes optional start hooks in registration order. An attempted service is included in rollback even when its start hook raises. Startup rollback re-raises the original failure and retains cleanup errors in `lifecycle_errors`. `stop_all()` invokes optional stop hooks in reverse attempted-start order, continues after hook or logging failures and returns failure records. Services without lifecycle hooks are allowed. A status label is not an independent health probe.

## `settings.py`

`Settings(storage=None, encode=None, decode=None)` is memory-only when constructed without storage. Composed runtimes inject storage and serialization. `start()` loads `/system/settings.txt`; `set()` and `delete()` write the versioned mapping before publishing memory changes. Persistent get/snapshot results are detached JSON data; standalone memory instances retain shallow reference semantics.

Keys must be non-empty strings. Persistent values must be plain JSON-compatible data with text mapping keys; unsupported objects, tuples and non-finite numbers are rejected. Stop marks offline because mutations already write through. Methods are not independently lifecycle-gated for trusted callers.

## `archive.py`

`Archive(storage, encode=None, decode=None)` stores named full user-file snapshots. Supplying both serialization callbacks enables the persistent index at `/system/archive/index.txt`; omitting both retains standalone memory behavior.

`save()` replaces an existing name. Snapshots exclude `/logs` and `/system`; restore preserves both prefixes. This prevents recursive archiving of the index and prevents restoring user files from rolling back service state. Restore is not transactional across files. A large index consumes memory and disk; there is no incremental snapshot format.

## `updates.py`

`Updates(storage=None, encode=None, decode=None)` stages unique names and source text. With injected storage it loads and writes `/system/updates/index.txt`. `inspect()` returns a new record with `applied: False` and `authenticated: False`. Empty source is allowed. No download, authentication, installation or execution path is introduced.

## Persistence and adapters

Services import only lower-layer schema definitions. They receive encode/decode callbacks from composition rather than importing JSON. The host serialization adapter owns standard-library use. All state documents carry the stored-data format and a document kind. Unknown formats and corrupt documents are refused, not silently reset.

Disk runtimes retain service state across new kernels. Memory runtimes use the same document semantics but lose their entire backend with the instance. Index writes are single-file replacements through storage, not fsync durability, multi-file transactions or concurrent-writer protection.

## Tests

`tests/test_services.py` covers local registry/settings/archive/update operations. Cross-runtime persistence and lifecycle failure tests live in `../kernel/tests/test_architecture.py`.
