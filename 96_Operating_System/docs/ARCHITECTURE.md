# BrisartOS Architecture

BrisartOS is a host-Python research operating environment with explicit assembly, lifecycle, persistent service state and trusted module contracts.

## Dependency direction

| Directory | Layer | Responsibility |
| --- | --- | --- |
| `common/` | 0 | Identifier validation |
| `storage/` | 0 | Path policy, text storage, memory backend, data schema and shared state documents |
| `events/` | 1 | Structured recent events and per-source text logs |
| `host/` | 1 | Clock, entropy, arguments, terminal, disk, loading and JSON serialization |
| `language/` | 1 | Lexer, parser and restricted interpreter |
| `services/` | 1 | Service records, lifecycle and stateful built-ins |
| `extensions/` | 2 | API compatibility, facades, manifests and module lifecycle |
| `machine/` | 2 | Source-ROM lifecycle, cooperative tasks, device queues and platform facts |
| `kernel/` | 3 | Explicit assembly and runtime lifecycle |
| `shell/` | 4 | Commands, dispatch and interactive console |

Paths are relative to brisartos/. Imports stay within a directory or point strictly downward, never sideways between equal layers. Root version.py is a separately permitted dependency. Standard-library runtime imports, selected file and execution built-ins and the terminal functions print and input remain in host/. The audit also reports product strings that repeat the reserved runtime path prefixes, which storage/schema.py owns. The audit checks syntax and selected operations, not a complete host-isolation boundary; host/terminal.py still wraps the host input and print, and trusted modules remain host-capable.

## Assembly versus lifecycle

`kernel/composition.py` constructs a concrete RuntimeComponents bundle. It joins Storage with a memory or disk backend, builds EventLog with a host clock, registers settings/archive/updates with injected serialization callbacks, creates the console/device registry, builds ModuleContext/ModuleRegistry and supplies the interpreter and scheduler. The scheduler, devices and platform it assembles come from machine/. The builder does not start services and leaves the module context closed.

`kernel/kernel.py` accepts the bundle or builds one by default. It owns the normal lifecycle `created -> starting -> running -> stopping -> stopped`. Startup validates the stored-data marker, starts services in registration order, records kernel startup, opens the module context to module calls and optionally discovers modules. Startup exceptions trigger cleanup and are re-raised. A stopped instance cannot restart.

The explicit bundle is an injection seam, not a generic dependency container. Callers supplying custom components must preserve the documented interfaces and coherent shared references.

## Service lifecycle

ServiceRecord stores name, object, persistent and state. Registry registration order determines startup order; shutdown reverses attempted starts. Optional start/stop hooks allow simple objects without a base class. A failed start includes the attempted service in rollback. Rollback failures remain in lifecycle_errors while the original startup exception propagates.

Kernel shutdown sets stopping, closes the module context, cancels/closes pending iterators, invokes module cleanup hooks, stops services and attempts a final kernel event. Failures are collected in shutdown_errors; later phases still run and state becomes stopped. A hook that never returns cannot be interrupted. Trusted direct component access is not universally lifecycle-gated.

## Stored-data ownership

Program release version remains solely in root version.py. `storage/schema.py` owns `brisartos.data.v1` and the marker `/system/state/format.txt`. Existing text trees without a marker receive one without rewriting user files. Unknown markers are refused. There is no automatic migration to or from incompatible data formats.

Versioned service envelopes contain format, kind and payload. JSON is encoded/decoded by host/serialization.py and injected into services, so service modules do not import standard-library serializers. Plain JSON-compatible data with text mapping keys is accepted; unsupported objects, tuples and non-finite numbers are rejected. Corrupt or incompatible documents fail startup instead of being reset.

| State | Owner | Disk behavior |
| --- | --- | --- |
| User files and text logs | Storage | Retained under data/ |
| Settings | Settings | `/system/settings.txt` |
| Named user-file snapshots | Archive | `/system/archive/index.txt` |
| Update source candidates | Updates | `/system/updates/index.txt` |
| Format marker | Storage schema | `/system/state/format.txt` |
| Recent structured events and sequence total | EventLog | Instance-local only |
| Task records and iterators | Scheduler | Instance-local only |
| Module globals | Loaded Python object | Until replacement or process exit |

Memory mode uses the same state-document semantics but its backend disappears with the instance. Standalone Settings()/Updates() and Archive(storage) without serialization retain their memory-only use cases.

Mutations serialize and write before publishing memory changes. Settings returns detached values in composed mode. Archive excludes and preserves `/logs` and `/system`, avoiding recursive index snapshots and leaving settings/candidates unchanged during user-file restoration. The reserved prefix is a convention, not an access-control boundary.

Disk writes use sibling replacement; append is direct. No fsync durability, cross-process locking, secure temporary-file creation or multi-file transaction is provided. Snapshot restore can partially apply after backend failure. Back up data before adopting changed state semantics.

## Module compatibility and manifests

New modules declare manifest.txt beside module.py. The host loader returns the manifest text without interpreting it, and extensions/manifest.py parses that inert key/value text. Registry validates required fields, safe names, permissions, duplicates and API compatibility before executing Python. Malformed manifests do not fall back to legacy loading. After import, run must be callable; optional stop must also be callable.

The API contract is `(name, major, required_minor)`: name must be brisartos.module, major must match and runtime minor must meet or exceed required_minor. Minor changes are for compatible additions; breaking changes require a new major. The contract identifier is independent of the program release.

Required fields are name, display_name, version, author, description, api, api_major, api_minor, permissions and entry. Entry is run; version=runtime resolves the central release value. Manifest metadata is authoritative when present.

Legacy declaration-only modules retain the brisartos.module.v1 path and eight required Python declarations. They execute before validation. Optional MODULE_API declares explicit compatibility; otherwise the baseline is assumed. The unchanged legacy ABI does not establish compatibility with older releases that reused it.

Source folders under root modules/ are distinct from runtime `/modules/NAME/` data. Manifest validation is not authentication or hostile-code isolation. All Python shares one host process.

## Module service boundary and cleanup

ModuleContext holds storage, services, events, platform and work acceptance. ModuleAPI gates declared operations and returns SettingsAccess, ArchiveAccess or UpdatesAccess rather than live service objects. Facades expose operational methods, not start/stop. Unknown services require an explicit facade implementation. Private references remain reachable to trusted Python code.

Module runs record structured start/finish/failure events. Optional stop() hooks run without arguments in reverse registration order during shutdown. Acceptance is already closed, so hooks should release owned resources rather than request new gated API work. Reload retains code registrations and replaces discovered entries; it is not transactional and does not guarantee old-resource cleanup.

## Event ordering

EventLog entries contain sequence, time, source, kind, message and details. Details are copied on input and output. The text append succeeds before total/recent are published; failed appends leave no new in-memory entry but may have partially changed the backend.

Core kinds cover kernel start/stop, module load/rejection/start/finish/failure, service start/stop and task spawn/finish/failure. Existing text log display remains TIME SOURCE: MESSAGE. Kind/details are not persisted as structured records. Recent history is bounded, text files are not rotated, and sequence numbers restart per instance.

## Ownership of shared rules

Each shared rule has one owner so a change touches one place. Reserved runtime path prefixes (/logs, /system, /modules) and the stored-data format are defined in storage/schema.py, and the audit rejects product code that repeats those prefixes as string literals. Versioned state documents are read and written by storage/state.py, which settings, archive and updates all use instead of repeating the logic. Manifest structure is defined in extensions/manifest.py; host/loader.py only returns text. Product code reaches the terminal only through host/terminal.py. machine/ holds objects that do not depend on the kernel (scheduler, device queues, platform declarations, source-ROM lifecycle) so the kernel directory contains only assembly and lifecycle.

## Execution paths

Root run.py is a routing table that launches child interpreters from the project root; test discovery and aggregation live in tools/runtests.py. Console startup/banner/input are inside cleanup scope. TextConsole carries commands and results between host/terminal.py and Shell. Ordinary command errors are displayed; base exceptions propagate after cleanup.

The language remains a restricted parser/interpreter with selected step/growth limits, not arbitrary Python execution or comprehensive resource isolation. `machine/machine.py` owns the source-ROM lifecycle; the old language.rom import is removed, while run.py rom remains supported.

The scheduler in machine/ advances iterators cooperatively and closes cancelled iterators where possible. It cannot preempt a non-yielding task. Shell exposes task inspection/stepping, not task spawning. Platform flags remain declarations: no hardware boot, native code generation or self-hosting is introduced.

## Maintainer decisions and release gate

Keep explicit domain boundaries, implicit namespace packages, root version ownership and the six-section Python headers. Do not add a generic core/utils directory or dependency-injection framework. Add a domain only with a distinct responsibility, README, tests and audited layer placement.

Run tests and audit before edits. After edits refresh headers, review the diff, rerun tests/audit/header check and manually review changed prose. Update the first changelog release heading with the central version. Review data-format and module-API compatibility independently; changing program version performs no migration.

README files own local behavior; this page owns cross-domain flows and decisions. Static relationship lines are not measured execution coverage. Passing tests establish checked behavior on the interpreter used, not universal compatibility, security or bootability.

See [the runtime map](../brisartos/README.md) and [the changelog](CHANGELOG.md).
