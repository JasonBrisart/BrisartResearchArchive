# Kernel and Owned Components

This directory contains runtime composition, cooperative scheduling, device queues and declared platform capabilities.

## `kernel.py`: construction and lifecycle

`Kernel(data_root=None, modules_path=None, max_steps=10000, event_limit=1000)` constructs its component objects. With no data root it builds `Storage` over its memory backend; with a root it supplies the host disk backend instead. Storage itself lives in [`../storage/`](../storage/README.md). Construction also registers a text-console device but does not start services.

The lifecycle is `created` → `running` → `stopped`. `start()` registers settings, archive and updates, changes state, logs startup and optionally discovers modules. `stop()` cancels waiting tasks, logs shutdown and changes state. A second start or a stop outside the running state raises `RuntimeError`; restarting a stopped instance is unsupported.

`reload_modules()` returns discovery failures and records each reason. `run_file(path)` reads stored text and passes it to the language interpreter. `describe()` reports state, platform, module ABI, storage, services, modules and cumulative event count.

`kernel.events` is an [`EventLog`](../events/README.md) built from the kernel's storage, the host clock and `event_limit`. The kernel records its own start, stop and module-load failures there, and `describe()` reports its `total`. Startup and shutdown are not rollback transactions.

The module system is not given the kernel. Construction builds a `ModuleContext` holding the storage, the service registry, the event log and the platform facts, and passes that to the [module registry](../extensions/README.md). Modules can reach those four objects and nothing else the kernel owns.

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

## `devices.py`: registration and queued text

`DeviceRegistry` accepts unique non-empty string names and non-None objects. `get()` raises `CapabilityUnavailable` for an unknown name; `names()` sorts registered names. No driver interface is enforced.

`TextConsole.feed()` queues text, `read()` consumes the oldest input and `write()` appends output. `output()` copies the output list; `drain()` returns the pending output lines and empties the list. The shell console feeds each terminal line into this device and prints what it drains, so the device carries the interactive session. Non-text input/output raises `TypeError`; an empty input queue raises `EOFError`. Queues are unbounded and have no synchronization.

## `platform.py`: explicit capability declarations

`Platform.describe()` returns a new dictionary declaring host-interpreter execution, no hardware target, no native code generation, no third-party packages and `bootable: False`. It does not probe the machine. `boot_media()` and `firmware_handoff()` always raise `CapabilityUnavailable`.

## Local regression coverage

`tests/test_kernel.py` covers composition and lifecycle behavior. `tests/test_components.py` covers the scheduler, the console queues and draining, device registration and platform declarations. These checks do not establish concurrent operation or hardware boot.
