# BrisartOS

A Python research operating environment with a composed kernel, text storage, cooperative tasks, services, modules, a command shell and a restricted source language.

BrisartOS currently runs inside a host Python interpreter. It does not boot hardware, generate boot media or provide an independent runtime. The source uses the standard library and local modules, with no third-party package requirement.

## Start here

Run these commands from the directory containing `run.py`:

```bash
python -B run.py start
python -B run.py start --memory
```

The first command keeps text files and logs in `data/`. The second keeps them in memory for that session. Settings, saved snapshots and staged update candidates are memory-only in either mode. Deleting `data/` deletes the files and logs stored there; it is not a harmless cache cleanup.

The console accepts one command per line. Enter `help` to see its registered commands and `exit` to stop the session. The [shell README](brisartos/shell/README.md) owns command syntax and console behavior.

## Files at this level

`run.py` is the command router. It launches the console, the source-ROM demonstration and maintenance tools in child interpreters. Its test command discovers test folders, applies optional path-substring filters and aggregates results. Child programs run from the project root, even if the router was invoked elsewhere.

`version.py` contains the release string `__version__`. It is imported by version-reporting components; it does not compare versions or migrate stored data.

| Directory | What belongs there |
| --- | --- |
| [brisartos/](brisartos/README.md) | Runtime implementation, divided by responsibility |
| [modules/](modules/README.md) | Shipped drop-in module folders |
| [tests/](tests/README.md) | Repository-wide layout, version and documentation checks |
| [tools/](tools/README.md) | Static audit and Python-header maintenance |
| [docs/](docs/ARCHITECTURE.md) | Cross-directory architecture and the change record |

## Maintenance entry points

| Invocation | Router behavior |
| --- | --- |
| `python -B run.py test` | Run all discovered test folders |
| `python -B run.py test kernel shell` | Run folders matching either substring |
| `python -B run.py audit` | Print the static audit report |
| `python -B run.py headers` | Refresh syntax-derived header content |
| `python -B run.py rom` | Execute the source-ROM lifecycle demonstration |

Only `start` forwards extra options to its child program. Test filters that match nothing return status 2. A failing test folder makes the router return status 1. The `-B` flag suppresses bytecode-cache creation; it does not change storage mode.

## Runtime requirement

This documentation pass was checked with Python 3.12.15. Compatibility across other interpreter versions was not established by that run. A host Python interpreter remains necessary for every entry point.

The [architecture page](docs/ARCHITECTURE.md) explains how components connect. The [changelog](docs/CHANGELOG.md) records this documentation pass without claiming new runtime features.
