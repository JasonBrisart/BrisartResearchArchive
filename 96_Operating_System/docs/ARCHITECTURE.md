# BrisartOS Architecture

The runtime is composed from local components with explicit import layers, shared storage and a single-process execution model.

This page explains connections across directories. Each directory README owns the behavior of its local files; this page does not duplicate their method-by-method reference.

## Dependency direction

| Directory | Layer | Responsibility at the boundary |
| --- | --- | --- |
| `common/` | 0 | Identifier validation shared by callers |
| `storage/` | 0 | Path policy, text-file API and in-memory backend |
| `host/` | 1 | Host-backed values, disk backend and entry-file execution |
| `language/` | 1 | Source text to parsed nodes and execution results |
| `services/` | 1 | Registry and stateful service objects |
| `extensions/` | 2 | Module metadata, permissions, discovery and invocation |
| `kernel/` | 3 | Component construction and lifecycle coordination |
| `shell/` | 4 | Commands, dispatch and interactive console |

These paths are relative to `brisartos/`. Runtime imports may stay within a directory or point to a strictly lower layer, not sideways to an equal layer. The root-level version module is permitted separately.

Objects can be supplied without importing their implementation. The module registry and API receive a kernel object. The archive service receives a storage object. This keeps their static imports below the composition layer without making the supplied objects inaccessible at runtime.

Storage sits at layer 0 because it imports nothing and every layer above uses it. Its disk backend is the one exception kept in `host/`, since only that directory may touch the real filesystem; the kernel joins the two by passing the disk backend into `Storage`.

The runtime directory is named `extensions/` and the project-root folder of drop-in modules is named `modules/`, so the code that loads modules and the modules it loads are never confused. Module files still declare `MODULE_*` names and the `brisartos.module.v1` ABI.

The audit checks source-level import direction and selected host-only operations. It does not prove that every host interaction passes through an adapter: the console reads and prints with built-in input/output, and trusted module files execute as ordinary code.

## From router to prompt

The root `run.py` launches the console in a child interpreter whose working directory is the project root. The console chooses a data root or memory mode and supplies the module-source directory to Kernel.

Kernel construction creates storage, scheduler, device registry, text console, service registry, module registry, interpreter and platform declarations. Startup registers the three built-in services, changes lifecycle state, logs startup and optionally discovers modules.

The console prints the banner and discovery failures before entering its input loop. Each terminal line is fed to the kernel's TextConsole device. The console's `serve` function reads queued lines back from the device and passes each to Shell, which selects a registered command handler. The handler calls the supplied kernel or one of its components and returns display text, which `serve` writes to the device; the loop prints what it drains.

`serve` catches ordinary command exceptions and writes their type and message to the device. Prompt EOF or interrupt ends the loop. A finally clause stops a still-running kernel after that loop block has been entered. Construction, startup and banner failures occur before the cleanup block and are not covered by it.

## Source modules and stored module data

Module source files are discovered as immediate child `NAME/module.py` entries under the configured module-source directory. Discovery executes a file before checking its declarations, ABI and permissions. Ordinary load failures are recorded per folder; base exceptions are not caught by discovery.

Registered entries run through ModuleRegistry with a ModuleAPI carrying their declared permissions. The API prefixes file operations with `/modules/NAME/`. This namespace is stored data, distinct from the source directory containing module.py.

Permissions constrain API calls, not the process. A loaded module can bypass the API using capabilities available to the running interpreter. There is no process isolation or hostile-code sandbox.

## One storage interface, two backends

Storage owns path normalization and text validation. Its default MemoryBackend holds dictionary entries. The disk backend resolves paths below a root directory and stores UTF-8 files. Kernel chooses between them from its data-root argument.

Both backends implement read, write, append, delete, exists, paths and describe. Shared storage tests exercise the same contract against each. This supports common behavior for checked operations, not identical behavior under every host failure or filesystem condition.

Disk replacement writes use a temporary sibling followed by replace. Appends write directly. There is no lock, explicit flush-to-disk step or multi-file transaction. Path checks reject resolved targets outside the root but do not establish a race-free security boundary against concurrent filesystem mutation.

## State lifetimes

| State | Owner | Persistence provided by this implementation |
| --- | --- | --- |
| Text files and log files | Storage backend | Disk mode retains them; memory mode does not |
| Recent events and cumulative event counter | Kernel instance | None across new instances |
| Settings values | Settings instance | None |
| Named snapshots | Archive instance | None |
| Update candidates | Updates instance | None |
| Module-level variables | Loaded module object | Retained between runs; discovery reload creates new objects |
| Task records and iterators | Scheduler instance | None |

The kernel bounds recent events but not disk log size. Log insertion updates memory before appending the file line, so an append error can leave the two representations inconsistent.

Archive snapshots exclude `/logs`, and restoration keeps that prefix. This protects logs from that restore operation, not from all callers: the general storage interface still permits writes and deletions. Restore validates input before mutation but applies backend changes individually, so application failures can leave partial state.

## Execution paths that remain separate

The restricted language parses and evaluates its own tuple nodes. Its execution budget counts statements, expressions and loop iterations. Selected addition/multiplication guards do not constitute comprehensive resource isolation. The source-ROM model wraps that interpreter in lifecycle states and explicitly reports no hardware boot.

The scheduler advances supplied iterators cooperatively. The shell exposes task inspection and stepping but has no task-spawn command. The TextConsole device carries the interactive session, but terminal reading and printing still happen in the console loop. These distinctions matter when interpreting component status: implemented objects are not automatically integrated into every entry point.

Platform capabilities are fixed declarations. Boot-media and firmware-handoff methods always raise. No path in this architecture produces an independently bootable system.

## Evidence and documentation ownership

Directory READMEs describe local implementations. Python headers retain the six required sections and combine authored explanations with generated syntax facts. The header tool's relationship graph is static: router references can appear as importers, and test imports are not measured execution coverage.

The static audit checks configured structural rules. Repository tests additionally check links, fences, README openings and extracted Python examples. Non-Python console transcripts and shell-command header examples are not automatically executed by those example tests.

A passing audit is evidence for its checks, not a semantic review of prose. Test results apply to the interpreter and environment used for the run; they do not establish universal platform compatibility, security or bootability.

See the [runtime directory map](../brisartos/README.md) for local pages and the [change record](CHANGELOG.md) for this documentation revision.
