# Source Machine Lifecycle

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

The import moved from the language domain to `brisartos.machine.machine`. `python -B run.py rom` remains the launcher. There is no old-path compatibility shim. The directory is layer 2 and imports the lower language layer. It does not replace Python, boot hardware or provide self-hosting.

`tests/test_machine.py` retains the lifecycle, source/step-limit, fault, snapshot and instance-independence scenarios from the former ROM test file. Tests do not validate firmware or hypervisors.
