# Kernel and Owned Components

This directory contains runtime composition, text-storage policy, cooperative scheduling, object handles, device queues and declared platform capabilities.

## `kernel.py`: construction and lifecycle

`Kernel(data_root=None, modules_path=None, object_capacity=1024, max_steps=10000, event_limit=1000)` constructs its component objects. With no data root it selects memory storage; with a root it constructs the disk backend. Construction also registers a text-console device but does not start services.

The lifecycle is `created` → `running` → `stopped`. `start()` registers settings, archive and updates, changes state, logs startup and optionally discovers modules. `stop()` cancels waiting tasks, logs shutdown and changes state. A second start or a stop outside the running state raises `RuntimeError`; restarting a stopped instance is unsupported.

`reload_modules()` returns discovery failures and logs each reason. `run_file(path)` reads stored text and passes it to the language interpreter. `describe()` reports state, platform, module ABI, storage, memory, services, modules and cumulative event count.

`log(source, message)` validates the source name, assigns a sequence number, retains the newest `event_limit` events and appends a timestamped line to `/logs/SOURCE.log`. File logs are not rotated. The in-memory event is added before the file append, so an append failure can leave an event without its matching file line. Startup and shutdown are not rollback transactions.

## `storage.py`: canonical paths and file operations

`Storage` delegates to a supplied backend or creates `MemoryBackend`. The public operations are `write`, `append`, `read`, `delete`, `exists`, `list_files`, `snapshot`, `restore` and `describe`.

`normalize()` removes empty and `.` components and returns one leading slash. It rejects non-text or empty input, backslashes, NUL, `..` and paths with no file component. Writes and appends require string content.

`MemoryBackend` keeps text in a dictionary. Directory structure is implicit in path prefixes, and a file cannot simultaneously be a directory prefix. Listings are sorted. Missing reads and deletions raise `FileNotFoundError`.

`Storage.snapshot(exclude=())` returns file contents outside excluded prefixes. `restore(snapshot, keep=())` validates the mapping, text values, canonical duplicates and file/directory conflicts before changing files. It ignores replacement entries inside kept prefixes, deletes obsolete unprotected files and writes replacements. Backend failures during that last phase can leave a partial result.

```python
from brisartos.kernel.storage import Storage

store = Storage()
store.write("notes/a.txt", "first")
saved = store.snapshot()
store.write("/notes/a.txt", "second")
store.write("/extra.txt", "temporary")
store.restore(saved)
assert store.snapshot() == {"/notes/a.txt": "first"}
```

## `scheduler.py`: one iterator advance per turn

`Scheduler.spawn(name, iterator)` creates a task record and queues its identifier. `step()` calls `next()` on the next waiting task and requeues it after a yield. `StopIteration` records a finished task and its return value; another `Exception` records a failed task and its error text.

`run(steps=100)` limits advances, not time. `cancel()` and `cancel_all()` remove waiting tasks but retain records. They do not explicitly close iterators. `describe()` and `status()` omit iterator objects from returned records.

```python
from brisartos.kernel.scheduler import Scheduler

scheduler = Scheduler()
task = scheduler.spawn("sample", iter([1, 2]))
assert scheduler.run() == 3
assert scheduler.describe(task)["state"] == "finished"
```

A non-yielding iterator blocks its call. There is no preemption, priority, timeout or record-pruning policy.

## `memory.py`: handles, not addresses

`ObjectMemory(capacity=1024)` stores object references under integer handles beginning at 1. `allocate()` returns a new handle; `read`, `write` and `release` require an existing exact integer handle. Released handles are not reused. A full table raises `MemoryError`; invalid handles raise `KeyError`.

`status()` reports entry count and capacity. Capacity is not measured in bytes, and mutable values remain shared references.

## `devices.py`: registration and queued text

`DeviceRegistry` accepts unique non-empty string names and non-None objects. `get()` raises `CapabilityUnavailable` for an unknown name; `names()` sorts registered names. No driver interface is enforced.

`TextConsole.feed()` queues text, `read()` consumes the oldest input and `write()` appends output. `output()` copies the output list. Non-text input/output raises `TypeError`; an empty input queue raises `EOFError`. Queues are unbounded and have no synchronization.

## `platform.py`: explicit capability declarations

`Platform.describe()` returns a new dictionary declaring host-interpreter execution, no hardware target, no native code generation, no third-party packages and `bootable: False`. It does not probe the machine. `boot_media()` and `firmware_handoff()` always raise `CapabilityUnavailable`.

## Local regression coverage

`tests/test_kernel.py` covers composition and lifecycle behavior. `tests/test_storage.py` applies one storage contract to memory and disk backends. `tests/test_components.py` covers object memory, scheduler, devices and platform declarations. These checks do not establish concurrent operation or hardware boot.
