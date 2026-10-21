# Kernel Composition and Lifecycle

This directory assembles runtime components, coordinates lifecycle, advances cooperative tasks and provides device queues and platform declarations.

## Files and ownership

- `composition.py` owns `RuntimeComponents` and `build_runtime()`. It constructs storage, platform, events, services, devices, console, modules, interpreter and scheduler. It registers settings, archive and updates in that order, but starts none of them. `modules_path` is retained in the builder signature for call compatibility; discovery is controlled by Kernel.
- `kernel.py` owns `Kernel`. Its constructor accepts the existing options plus `components=None` for explicit injection. It delegates default assembly to the builder rather than constructing subsystems itself.
- `scheduler.py` owns iterator task records, round-robin stepping, cancellation and structured task events. A cancelled iterator is closed when it exposes `close()`; close and event failures are retained in `cleanup_errors`.
- `devices.py` owns `DeviceRegistry` and `TextConsole`. These remain named Python objects and text queues, not hardware drivers.
- `platform.py` owns fixed execution declarations and `CapabilityUnavailable`. Boot media and firmware handoff remain unavailable.

## Lifecycle

The normal path is `created -> starting -> running -> stopping -> stopped`. A failed start goes through stopping and ends stopped while re-raising the original exception. An instance starts only once.

Startup validates the stored-data marker, starts services in registration order, records `kernel.started`, accepts module calls and optionally discovers modules. Service startup events precede the kernel-start event.

Shutdown first sets stopping and refuses permission-gated module calls and new module runs. It then cancels/closes pending tasks, invokes module `stop()` hooks in reverse registration order, stops services in reverse startup order and attempts the final `kernel.stopped` event. Each cleanup phase continues after ordinary or base exceptions. `stop()` returns failure records, also retained in `shutdown_errors`; the state becomes stopped even when final logging fails. Hooks that never return cannot be interrupted.

```python
from brisartos.kernel.composition import build_runtime
from brisartos.kernel.kernel import Kernel
components = build_runtime()
kernel = Kernel(components=components)
kernel.start()
assert kernel.storage is components.storage
assert kernel.stop() == []
assert kernel.state == "stopped"
```

`run_file()` and `reload_modules()` require running state. `describe()` retains its seven fields; service lifecycle metadata is available through the service registry. Runtime objects remain trusted and directly accessible to internal callers.

## Cooperative tasks and devices

`Scheduler.spawn(name, iterator)` queues a task; `step()` advances one iterator and `run(steps)` limits advances, not time. Completed, failed and cancelled records remain available. Task events use `task.spawned`, `task.finished` and `task.failed`. There is no preemption, timeout, priority or record-pruning policy.

`TextConsole.feed()` queues input, `read()` consumes it, `write()` appends output and `drain()` hands over and clears output. Queues are unbounded and unsynchronized. The shell console still uses host terminal input/output around this device.

## Tests

`tests/test_kernel.py` checks lifecycle, composition wiring, event limits, stored programs and disk files. `tests/test_components.py` checks scheduler/device/platform behavior. `tests/test_architecture.py` checks injected composition, persistent services, schema rejection, manifest prevalidation, API compatibility, facades, event ordering and cleanup failures. These are host-process tests, not hardware validation.
