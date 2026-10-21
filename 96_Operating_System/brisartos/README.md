# BrisartOS Runtime Package

The runtime source is divided into ten responsibility-based directories; no executable Python file sits directly in this directory.

## Directory boundaries

| Directory | Local responsibility | Import layer |
| --- | --- | --- |
| [common/](common/README.md) | Shared identifier validation | 0 |
| [storage/](storage/README.md) | Path policy, file API, in-memory backend, data schema and state documents | 0 |
| [events/](events/README.md) | Numbered events and per-source log files | 1 |
| [host/](host/README.md) | Clock, entropy, arguments, terminal, disk files, module loading and JSON serialization | 1 |
| [language/](language/README.md) | Tokenization, parsing and evaluation | 1 |
| [services/](services/README.md) | Shared service objects and their registry | 1 |
| [extensions/](extensions/README.md) | Module API, compatibility contracts, manifest parsing, registration and discovery | 2 |
| [machine/](machine/README.md) | Source-ROM lifecycle, cooperative scheduler, device queues and platform facts | 2 |
| [kernel/](kernel/README.md) | Explicit component assembly and runtime lifecycle | 3 |
| [shell/](shell/README.md) | Command registration, dispatch and interactive input | 4 |

A runtime file may import within its own directory or from a strictly lower layer. Equal-layer directories may not import one another. The root-level version module is a separate permitted dependency.

The static audit restricts standard-library imports, selected direct execution/file calls, the terminal built-ins `print` and `input`, and bytes literals to `host/` within product code. It also reports product strings that repeat the reserved runtime path prefixes owned by `storage/schema.py`. These are source-organization checks, not proof that all host interaction is isolated: `host/terminal.py` still wraps the host input and print, and loaded module code executes in the same process.

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
