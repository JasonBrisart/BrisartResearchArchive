# Kernel Composition and Lifecycle

This directory assembles the runtime components and coordinates their lifecycle. The scheduler, device queues and platform declarations it assembles live in [the machine directory](../machine/README.md).

## Files and ownership

- `composition.py` owns `RuntimeComponents` and `build_runtime()`. It constructs storage, platform, events, services, devices, console, modules, interpreter and scheduler, taking the scheduler, devices and platform from `brisartos/machine/`. It registers settings, archive and updates in that order, leaves the module context closed and starts nothing. `modules_path` is retained in the builder signature for call compatibility; discovery is controlled by Kernel.
- `kernel.py` owns `Kernel`. Its constructor accepts the existing options plus `components=None` for explicit injection. It delegates default assembly to the builder rather than constructing subsystems itself.

Nothing else lives here. The kernel is the only layer-3 component and depends on lower layers only; none of the objects it assembles depend on it.

## Lifecycle

The normal path is `created -> starting -> running -> stopping -> stopped`. A failed start goes through stopping and ends stopped while re-raising the original exception. An instance starts only once.

Startup validates the stored-data marker, starts services in registration order, records `kernel.started`, calls `open()` on the module context so module calls are accepted, and optionally discovers modules. Service startup events precede the kernel-start event.

Shutdown first sets stopping and calls `close()` on the module context, which refuses permission-gated module calls and new module runs. It then cancels/closes pending tasks, invokes module `stop()` hooks in reverse registration order, stops services in reverse startup order and attempts the final `kernel.stopped` event. Each cleanup phase continues after ordinary or base exceptions. `stop()` returns failure records, also retained in `shutdown_errors`; the state becomes stopped even when final logging fails. Hooks that never return cannot be interrupted.

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

## Tests

`tests/test_kernel.py` checks lifecycle, composition wiring, event limits, stored programs and disk files. `tests/test_architecture.py` checks injected composition, persistent services, schema rejection, manifest prevalidation, API compatibility, facades, event ordering and cleanup failures. Scheduler, device and platform tests live in `../machine/tests/test_components.py`. These are host-process tests, not hardware validation.
