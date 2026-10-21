# Machine Primitives and Source-ROM Lifecycle

This directory holds the runtime's machine-level objects: the source-ROM lifecycle model, the cooperative scheduler, the device registry with its text-console queues, and the fixed platform capability declarations. None of them depends on the kernel; [the kernel](../kernel/README.md) assembles them.

## `machine.py`: source-ROM lifecycle

`machine.py` wraps the restricted language in an explicit reset/running/halted/faulted lifecycle without claiming firmware boot.

`SourceROMMachine` validates source size and interpreter limits, parses once and creates a fresh interpreter for each boot attempt. Successful execution halts; an ordinary execution failure records fault text, preserves partial output/variables/steps and re-raises. Reset clears results but preserves source and attempt count. Snapshot containers are copied.

```python
from brisartos.machine.machine import SourceROMMachine
machine = SourceROMMachine("print(4)")
assert machine.boot()["output"] == ["4"]
assert machine.snapshot()["hardware_boot"] is False
machine.reset()
assert machine.boot()["boot_attempts"] == 2
```

`main()` writes its report through `host/terminal.py`, and `python -B run.py rom` is the launcher. The import path is `brisartos.machine.machine`; there is no compatibility shim for the former language location. It does not replace Python, boot hardware or provide self-hosting.

## `scheduler.py`: cooperative tasks

`Scheduler.spawn(name, iterator)` queues a task; `step()` advances one iterator and `run(steps)` limits advances, not time. Completed, failed and cancelled records remain available. A cancelled iterator is closed when it exposes `close()`; close and event failures are retained in `cleanup_errors`. When the scheduler is given an event log, task events use `task.spawned`, `task.finished` and `task.failed`. There is no preemption, timeout, priority or record-pruning policy.

## `devices.py`: registry and console queues

`DeviceRegistry` holds named device objects and raises `CapabilityUnavailable` for an unregistered name. `TextConsole.feed()` queues input, `read()` consumes it, `write()` appends output and `drain()` hands over and clears output. These are named Python objects and text queues, not hardware drivers. Queues are unbounded and unsynchronized. The shell console uses the host terminal around this device.

## `platform.py`: capability declarations

`Platform.describe()` returns fixed facts about the execution environment, including `bootable: False`. `boot_media()` and `firmware_handoff()` always raise `CapabilityUnavailable`. The facts are declarations, not probes of the machine.

## Layer and limits

This directory is layer 2. It imports only lower layers: the language interpreter and parser, and the terminal writer in `host/`. The kernel (layer 3) and the extension system receive its objects by construction or injection rather than by importing the kernel. None of this provides hardware access, hypervisor support or firmware handoff.

## Tests

`tests/test_machine.py` covers lifecycle, source/step limits, faults, snapshots and instance independence. `tests/test_components.py` covers scheduling order, failure and cancellation, console queues and draining, device registration and the platform refusals. Tests do not validate firmware or hypervisors.
