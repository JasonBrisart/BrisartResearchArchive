# BrisartOS Runtime Package

The runtime source is divided into eight responsibility-based directories; no executable Python file sits directly in this directory.

## Directory boundaries

| Directory | Local responsibility | Import layer |
| --- | --- | --- |
| [common/](common/README.md) | Shared identifier validation | 0 |
| [storage/](storage/README.md) | Path policy, file API and in-memory backend | 0 |
| [host/](host/README.md) | Clock, entropy, arguments, disk files and dynamic loading | 1 |
| [language/](language/README.md) | Tokenization, parsing, evaluation and source-ROM lifecycle | 1 |
| [services/](services/README.md) | Shared service objects and their registry | 1 |
| [extensions/](extensions/README.md) | Module registration, discovery and permission-checked API | 2 |
| [kernel/](kernel/README.md) | Runtime composition, scheduling, devices and platform facts | 3 |
| [shell/](shell/README.md) | Command registration, dispatch and interactive input | 4 |

A runtime file may import within its own directory or from a strictly lower layer. Equal-layer directories may not import one another. The root-level version module is a separate permitted dependency.

The static audit restricts standard-library imports, selected direct execution/file calls and bytes literals to `host/` within product code. These are source-organization checks, not proof that all host interaction is isolated: the interactive console uses built-in input and output, and loaded module code executes in the same process.

Each child directory has a `tests/` directory and its own README. Those pages explain local files and their contracts; the [architecture page](../docs/ARCHITECTURE.md) owns cross-directory flows.

## Importing this tree

These directories use implicit namespace packages, without package initializer or package-main files. Imports assume the project root is on the import path so the root-level version module can be found.

```python
from brisartos.kernel.kernel import Kernel
from brisartos.shell.shell import Shell

kernel = Kernel()
kernel.start()
shell = Shell(kernel)
assert shell.execute("write /answer.py print(6 * 7)") == "/answer.py"
assert shell.execute("python /answer.py") == "42"
kernel.stop()
```

This example connects existing components; it does not demonstrate firmware boot or process isolation.
