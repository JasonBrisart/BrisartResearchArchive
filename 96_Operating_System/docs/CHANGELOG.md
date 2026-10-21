All notable changes to BrisartOS are documented in this file.

BrisartOS is a pure-Python, dependency-free, fully custom operating
system research project.

---

## [0.0.15] - 2026-10-21

An architecture-ownership release. Each shared rule and each machine-level object now lives in the directory that owns it, and the rule that only `host/` touches the outside world is now checked for terminal input and output as well as files and imports.

The layer map is unchanged: no directory was added to or removed from it, and the dependency direction between the ten runtime directories is the same. What changed is placement. The scheduler, device registry and platform declarations left `kernel/` for `machine/`, manifest rules left `host/` for `extensions/`, the reserved runtime path prefixes and the repeated state-document logic were consolidated under `storage/`, and the terminal now has one named adapter in `host/`.

No stored-data format changed: `brisartos.data.v1`, the `/system` documents and the text logs are byte-for-byte what the previous release wrote. The module API (`brisartos.module` 1.0) and the manifest format are unchanged. There is no data migration. Several import paths and one function name changed; they are listed under Compatibility and residual risk.

BrisartOS remains a host-Python operating environment. No firmware boot, independent hardware execution or self-hosting capability is introduced.

### Added

- **`brisartos/storage/state.py`: `StateFile`, one implementation of a versioned state document.** `Settings`, `Archive` and `Updates` each carried their own copy of the same logic: read the file, decode it, check the envelope, then encode, write and round-trip a detached copy on every change. `StateFile(storage, path, kind, encode, decode)` now owns that. `load()` returns the validated payload, or `None` when no document exists; a document that fails validation still raises rather than being treated as empty. `save(values)` encodes before writing, writes once and returns a copy decoded from the written text. `detach(values)` copies plain data through the same callbacks without touching storage. It adds no locking, multi-file transaction or durability guarantee; `save` is one storage write.

- **`brisartos/extensions/manifest.py`: `parse_manifest`, `FIELDS` and `ENTRY`.** The manifest schema previously sat in `host/loader.py`: the allowed-field set, the `entry == run` rule, integer conversion and permission splitting were module-system policy living in the adapter layer. `parse_manifest(text)` now returns the ten fields with `api_major` and `api_minor` as integers and `permissions` as a tuple, and checks structure only. It does not judge names, permissions or API compatibility, which the registry still decides before any module code is imported.

- **`brisartos/host/terminal.py`: `read_line` and `write_line`.** Thin wrappers over the host `input()` and `print()`. `shell/console.py` and `machine/machine.py` previously called those built-ins directly, which the runtime README admitted was outside the host-only rule. They now give product code one name for the terminal. End of input and interrupts still reach the caller unchanged.

- **`brisartos/storage/schema.py`: `LOG_PREFIX`, `MODULES_PREFIX` and `PROTECTED_PREFIXES`.** The `/logs` prefix was defined as `LOG_FOLDER` in `events/events.py` and written again inside `Archive`'s protected tuple. The module storage prefix `/modules` was written twice inside `ModuleAPI`. Each is now defined once beside `SYSTEM_PREFIX`. `MODULES_PREFIX` is the runtime folder for each module's own files, not the project-root `modules/` source folder.

- **`ModuleContext.accepting`, `open()` and `close()` in `brisartos/extensions/api.py`.** The kernel and `build_runtime()` previously assigned `context.accepting = True` or `False` from outside the object. `accepting` is now a read-only property, and the kernel calls `close()` and `open()`.

- **`tools/runtests.py`.** Test discovery, concurrent per-folder execution and result aggregation moved here from `run.py`. Behavior is unchanged (see Changed).

- **Two audit rules in `tools/audit.py`.** `print` and `input` are added to the calls only `brisartos/host/` may make in product code. Separately, a product string that starts with `/logs`, `/system` or `/modules` is reported unless it is a docstring or sits in `brisartos/storage/schema.py`. The second rule is a literal check: it does not detect a prefix built by concatenation.

- **44 net new tests, 315 in total.** New files: `host/tests/test_terminal.py` (5), `storage/tests/test_state.py` (11), `extensions/tests/test_manifest.py` (11). Additions to existing files: 3 raw-manifest-text tests in `host/tests/test_loader.py`, 2 context open/close tests in `extensions/tests/test_api.py`, 4 state-persistence tests in `services/tests/test_services.py`, and 8 in `tools/tests/test_tools.py` (terminal built-ins, reserved literals, docstring exemption and four `runtests.py` exit-status tests).

### Changed

- **`scheduler.py`, `devices.py` and `platform.py` moved from `brisartos/kernel/` to `brisartos/machine/`, together with their tests.** None of the three depended on `Kernel`: `scheduler.py` and `platform.py` import nothing and `devices.py` imports only `platform.py`. Keeping them in `kernel/` made the kernel directory look like the owner of objects it merely assembles. `kernel/` now holds `composition.py` and `kernel.py` only. `machine/` stays at layer 2, so the kernel at layer 3 importing it is a downward import and the audit accepts it. File contents are unchanged apart from header `File:` lines, examples and import paths. `kernel/tests/test_components.py` moved to `machine/tests/test_components.py`.

- **`brisartos/host/loader.py`: `read_manifest(path)` replaced by `read_manifest_text(path)`.** The loader now returns the text of the sibling `manifest.txt` exactly as stored, or `None` when there is none. `ModuleRegistry.discover()` in `brisartos/extensions/registry.py` calls `parse_manifest` on that text and then runs the same name, permission, duplicate and API checks as before, all before `load_module`. A manifest with a non-integer `api_major` or `api_minor` is now refused with a message naming the field instead of the message from `int()`; a negative value was already refused, now at parse time.

- **`Settings`, `Archive` and `Updates` persist through `StateFile`.** Observable behavior is unchanged: same documents, same paths, same validation of persisted contents, same error messages for existing failures. Two small differences: `Archive` now publishes the decoded copy that `save` returns rather than the dictionary it built, and an `Archive` given non-callable callbacks now fails at construction with `state files require serialization callbacks` instead of at first use.

- **`events/events.py`, `services/archive.py` and `extensions/api.py` read their path prefixes from `storage/schema.py`.** `events.LOG_FOLDER` is removed. `services/archive.py` keeps its `PROTECTED` name as an alias of `PROTECTED_PREFIXES`, so existing imports of it still work. Recorded log paths, snapshot exclusions and module file paths are unchanged.

- **`brisartos/kernel/kernel.py` and `brisartos/kernel/composition.py` call `open()` and `close()` on the module context** in place of assigning `accepting`. Startup order, shutdown order and the closed-while-stopping behavior are unchanged.

- **`brisartos/shell/console.py` and `brisartos/machine/machine.py` write and read through `host/terminal.py`.** The console banner, prompt and output are identical. `machine.main()` now builds its three status lines with string concatenation instead of passing multiple arguments to `print`; the printed text is identical.

- **`run.py` is now only a routing table.** `test` is routed to `tools/runtests.py` as a child process like every other command, and `test` now forwards its options along with `start`. Exit statuses are unchanged: 0 when every folder passes, 1 when any fails, 2 when a filter matches nothing. The per-folder result lines and summary format are unchanged.

- **Documentation was updated against the new placement.** The runtime README, `docs/ARCHITECTURE.md` (including a new section on ownership of shared rules), the kernel, machine, host, extensions, storage, services, events, shell and tools READMEs, and the root README now describe the moved files, `terminal.py`, `manifest.py`, `state.py`, `runtests.py` and the two audit rules. Generic placeholder descriptions in the headers of files touched here were replaced: the six constants in `storage/schema.py`, `REQUIRED_NAMES` in `extensions/registry.py` and the three constants in `extensions/contracts.py`.

- **`version.py`: the central release string is now `0.0.15`.**

### Fixed

- **`brisartos/machine/tests/test_components.py`: the header listed a `MemoryTests` class and three scenarios that no longer exist.** The previous release entry stated this stale text had been corrected, but the file as exported still contained it. It is removed now, and the header's scenario list is regenerated from the classes actually present.

### Verification

- The previous release was reconstructed from its project export: all 69 files matched the SHA-256 values in the export manifest (one only after removing the extra trailing newline the export adds to each file block), and `python -B run.py test` on a clean copy gave 271 passed.

- After the changes, on Linux with Python 3.12.15 in a clean copy:

```text
PASSED: 315 tests in 12 folders
```

  Per folder: tests 15, common 4, events 7, extensions 43, host 28, kernel 34, language 38, machine 30, services 13, shell 31, storage 41, tools 31.

- `python -B run.py audit` reported PASS with no errors, and `python -B tools/headers.py --check` reported `all headers current`.

- A scripted 25-command console session in memory mode, covering files, a multi-line stored program, settings, snapshots, staging, services, modules, tasks and reload, produced output identical to the previous release apart from the release string. `python -B run.py rom` output was identical. In disk mode, a setting written in one console process was read back by a second process and was present in `data/system/settings.txt`.

Not verified in that environment: Windows or macOS execution, other Python versions, hypervisor or hardware boot, power-loss durability and concurrent-writer behavior.

### Compatibility and residual risk

- Import paths changed with no compatibility shim: `brisartos.kernel.scheduler`, `brisartos.kernel.devices` and `brisartos.kernel.platform` are now `brisartos.machine.scheduler`, `brisartos.machine.devices` and `brisartos.machine.platform`. Code that imports the old paths, or the old `brisartos.kernel.tests.test_components` location, must be updated.

- `brisartos.host.loader.read_manifest` and `brisartos.events.events.LOG_FOLDER` no longer exist. Use `read_manifest_text` with `parse_manifest`, and `LOG_PREFIX` from `brisartos.storage.schema`.

- `ModuleContext.accepting` can no longer be assigned. Callers that set it must call `open()` or `close()`.

- `run.py` no longer contains the test-runner functions. Code that imported them from `run.py` must use `tools/runtests.py` or call `python -B run.py test`.

- No stored-data format changed and no migration is needed. Existing `data/` folders written by the previous release load unchanged.

- The new audit rules can flag out-of-tree code that uses `print` or `input` inside `brisartos/` outside `host/`, or that hard-codes a reserved prefix. They apply to product code, not to loaded modules.

- `host/terminal.py` gives the host boundary one name; it does not isolate anything. Loaded module code is outside the `brisartos/` audit and can still call `print` or `input` directly. The reserved-prefix rule is a literal check and does not detect a prefix assembled from parts.

- `machine/` placement is organizational. The scheduler is still cooperative and in-process with no preemption or timeout, and the device and platform objects are still declarations and text queues, not hardware access.

- `StateFile` writes one file per document. It provides no cross-process locking, multi-file transaction or power-loss durability, and snapshot restore can still apply partially after a backend failure.

- No external dependencies were introduced. BrisartOS remains Python source using project modules and the Python standard library, and still requires a host Python interpreter.

---

## [0.0.14] - 2026-10-21

### Added
- Added an explicit RuntimeComponents bundle and build_runtime composition function so component wiring is separate from kernel lifecycle.
- Added ordered service start/stop hooks, lifecycle records, persistence metadata and reverse cleanup with retained failure records.
- Added an independent stored-data format marker and versioned state envelopes; unknown formats and corrupt state are refused instead of silently reset.
- Added injected host JSON serialization and write-through persistence for settings, named user-file snapshots and update candidates.
- Added manifest-first module loading so metadata, permissions and API compatibility can be rejected before executing new-format entries.
- Added explicit API name/major/minor compatibility checks while retaining legacy declaration-only loading as a trusted-code fallback.
- Added narrow settings, archive and update service facades for module access instead of returning live lifecycle objects.
- Added structured event kinds/details, task outcome events and append-before-publication event ordering.
- Added starting/stopping kernel states, optional module stop hooks, iterator close on cancellation and best-effort shutdown failure collection.
- Added architecture regression tests for persistence, compatibility, manifests, composition, event failure ordering and cleanup behavior.

### Changed
- Moved the source-ROM lifecycle model from language/rom.py to machine/machine.py and moved its tests; the root rom command is unchanged.
- Changed disk mode to retain settings, snapshots and staged candidates under /system; memory mode still discards all state.
- Changed archive snapshots to exclude and preserve both /logs and /system, preventing recursive snapshot indexes and service-state rollback.
- Changed service descriptions to include lifecycle state and persistence, and module descriptions to include explicit API requirements.
- Changed persistent settings to accept detached plain JSON-compatible values; standalone memory-only settings retain shallow reference behavior.
- Updated the audit layer map for machine and allowed only modules/NAME/manifest.txt as a narrow text-file exception.
- Updated affected Python headers, local READMEs, architecture guidance, maintainer workflow and shipped example metadata.

### Fixed
- Extended console cleanup scope to cover startup and banner failures as well as the input loop.
- Preserved the original startup failure while retaining cleanup errors and continuing later shutdown phases.
- Prevented a failed log append from publishing a new recent event or sequence total.
- Corrected stale component-test documentation referring to the removed object-memory implementation.

---

## [0.0.13] - 2026-10-20

### Added

- Added the `brisartos/events/` directory with `EventLog`, which numbers events, keeps a bounded list of recent ones and appends each to `/logs/SOURCE.log`. Event recording now has its own home instead of living inside the kernel.
- Added `ModuleContext` to the module API. It holds exactly what the module system may reach: storage, the service registry, the event log and the platform facts.
- Added tests for the event log that use memory storage and a fixed clock, with no kernel involved.
- Added tests showing that a module API works from a context built without a kernel, and that the kernel hands the module system a context rather than itself.
- Added a README for `brisartos/events/`.

### Changed

- Changed `ModuleRegistry` and `ModuleAPI` to take a `ModuleContext` instead of the kernel, so the layer-2 module system no longer depends on the shape of the layer-3 kernel object. `ModuleRegistry(kernel)` is now `ModuleRegistry(context)`, and `ModuleAPI(kernel, name, permissions)` is now `ModuleAPI(context, name, permissions)`.
- Changed `kernel.events` from a plain list to the kernel's `EventLog`. Read recent events with `kernel.events.recent(count)` and the running total with `kernel.events.total`.
- Changed the kernel, the module registry and the module API to record every event through the same `EventLog`. Log lines and file locations are unchanged.
- Changed the `logs` shell command to read from `EventLog.recent`. Its output is unchanged.
- Updated the audit layer map to place `events` at layer 1.
- Moved event-numbering and log-source tests from the kernel tests to `brisartos/events/tests/`; the kernel tests now check only that the kernel wires the event log in.
- Updated the kernel, extension-system, runtime-package, tools and architecture documentation for the event log and the module context.

### Removed

- Removed `Kernel.log`. Record events with `kernel.events.record(source, message)`.

## [0.0.12] - 2026-10-20

### Added

- Added the `brisartos/storage/` directory at layer 0 so the path policy and file API sit below every component that uses them.
- Added `TextConsole.drain()` so the console can collect pending output lines and empty the device's output list in one call.
- Added `serve(kernel, shell)` to the console so each command line passes through the kernel's console device on its way to the shell and back.
- Added tests for console draining and for commands, results and errors flowing through the console device.
- Added a README for `brisartos/storage/` describing the storage API, the memory backend and the contract tests.

### Changed

- Moved `storage.py` and its contract tests from `brisartos/kernel/` to `brisartos/storage/`. Storage imports nothing, so keeping it in the kernel made layer-1 code depend on a layer-3 directory in practice.
- Renamed the runtime module system from `brisartos/modules/` to `brisartos/extensions/` so it is no longer confused with the project-root `modules/` folder of drop-in modules. The `MODULE_*` declarations and the `brisartos.module.v1` ABI are unchanged, and existing module files load without edits.
- Changed import paths to `brisartos.storage.storage` and `brisartos.extensions.api` / `brisartos.extensions.registry`. Code importing the old `brisartos.kernel.storage` or `brisartos.modules.*` paths must be updated.
- Updated the audit layer map to place `storage` at layer 0 and `extensions` at layer 2.
- Changed the interactive console to feed each line into the kernel's `TextConsole` device and print what the device returns, so the registered console device now carries the session instead of sitting unused. Displayed output and error lines are unchanged.
- Removed the `object_capacity` parameter from `Kernel` and the `memory` entry from `Kernel.describe()`; the `system` command now shows seven lines instead of eight.
- Retargeted the maintenance-tool tests that edited the removed object-memory file to `brisartos/kernel/scheduler.py`.
- Rewrote the kernel, runtime-package, shell, extension-system and architecture documentation to match the new layout.

### Removed

- Removed `ObjectMemory` (`brisartos/kernel/memory.py`) and its tests. Nothing outside the tests used it; it can return when a component needs object handles.

## [0.0.11] - 2026-10-20

### Added

- Added a composed kernel with explicit lifecycle states to coordinate runtime startup, operation and shutdown.
- Added cooperative iterator scheduling with completion, failure and cancellation records to track task execution.
- Added capacity-limited object-handle storage to manage references through validated integer handles.
- Added device registration and queued text-console objects to represent named devices and buffered text input/output.
- Added a shared text-storage interface with memory and disk backends so callers can use the same file operations in either mode.
- Added normalized paths, file appending, snapshots and restoration to support consistent storage operations.
- Added a restricted source language with variables, expressions, assignment, branching, loops and captured output.
- Added execution-step limits and selected arithmetic-growth checks to constrain supported language operations.
- Added a source-ROM lifecycle model with reset, running, halted and faulted states to track execution attempts and preserve partial results after failures.
- Added named archive snapshots and restoration that preserves the log prefix, replacing the archive service's status-only implementation.
- Added settings lookup, assignment, deletion and shallow snapshots, replacing the settings service's status-only implementation.
- Added update-candidate staging, inspection and removal, replacing the update service's status-only implementation. Candidates are stored without authentication, installation or execution.
- Added shell commands for file operations, restricted-language execution, snapshots, settings and update candidates.
- Added shell inspection of devices, tasks, scheduler progress and recent events.
- Added a memory-only console option alongside disk-backed default operation.
- Added a root command router to provide one entry point for runtime and maintenance commands.
- Added a static architecture audit to check source layout, import boundaries and documentation requirements.
- Added a header-refresh tool to update syntax-derived documentation while retaining authored explanations.

### Changed

- Reorganized runtime code into `common`, `host`, `kernel`, `language`, `modules`, `services` and `shell` directories to separate responsibilities.
- Separated host-backed operations from runtime composition, module management and command handling to make dependency boundaries explicit.
- Split the interactive shell into command definitions, dispatch and console-loop implementations so each file has a narrower responsibility.
- Moved component tests beside their implementations while retaining repository-wide checks in the root test directory.
- Centralized release identification in the root-level `__version__` assignment, replacing `NAME`, `VERSION` and the version-formatting helper.
- Changed the release identifier from `0.10.0-alpha` to `0.0.11` and updated consumers to use the centralized value.
- Replaced the module permission `module_data` with `storage`.
- Bound module file operations and logging to the calling module's namespace instead of accepting a separate module or source name.
- Made module discovery alphabetical so entry processing follows a predictable order.
- Retained discovery failures by folder so individual load problems remain inspectable.
- Preserved code-registered modules during rediscovery while replacing discovered entries.
- Updated the shipped example module to write its file, store its identifier in settings and return a result summary.
- Retained `brisartos.module.v1` as the ABI identifier despite the module API changes; the unchanged identifier does not establish compatibility with the previous API.
- Rewrote Python headers around each file's actual purpose, interfaces, relationships, parameters, edge cases, limitations and examples.
- Retained the six ordered Python-header sections while replacing generic descriptions with implementation-specific explanations.
- Rewrote directory READMEs to describe their actual files and immediate child directories rather than repeat a shared template.
- Rewrote the architecture guide around dependency layers, execution flows, state ownership and persistence boundaries.
- Replaced hardware-oriented descriptions with explicit host-interpreter execution and unsupported boot-capability declarations.

### Fixed

- Preserved indentation in shell file-writing commands so stored programs can contain correctly indented blocks.
- Added ordinary command-error recovery so a failed command does not automatically end the interactive session.
- Added shutdown cleanup around the active console loop so a running kernel is stopped when that protected block exits.
- Added module permission-declaration validation to reject unsupported declarations before registration.
- Added safe-name validation and duplicate-registration rejection to prevent invalid or conflicting registry entries.
- Added failed module-execution logging before exceptions are re-raised.
- Corrected documentation that described API permissions as code isolation.
- Corrected documentation that implied disk replacement writes guarantee power-loss durability.
- Corrected documentation that implied console cleanup covers failures before the protected input loop.
- Corrected documentation that implied settings, archive snapshots or update candidates persist across runtime instances.
- Corrected documentation that described selected language-growth checks as comprehensive resource limits.
- Corrected documentation that claimed the shipped example exercises every module API method.
- Distinguished static import relationships from dynamic execution and measured test coverage.

### Removed

- Removed the browser implementation and its associated tests.
- Removed boot-sector generation, floppy-image generation and image inspection.
- Removed instruction-emitter and label-fixup implementations and their associated tests.
- Removed the previous runtime/SystemAPI implementation in favor of the composed kernel and module API.
- Removed duplicate platform descriptions to keep capability declarations in one implementation.
- Removed the separate filesystem service in favor of the shared storage interface.
- Removed the old centralized test runner and shared path-setup helper in favor of directory-local tests and the root command router.
- Removed unrelated project comparisons, speculative feature descriptions and examples that did not describe the delivered implementation.

---

## [0.10.0-alpha] - 2026-08-29
### Added
- Added a full automated test suite under `tests/`, built entirely on
  Python's standard library `unittest` module -- no pytest, no
  third-party test framework, and no new dependency of any kind,
  consistent with `docs/DEPENDENCY_POLICY.md`.
- Added `tests/_support.py`: shared, dependency-free test scaffolding
  (not itself a test module) that every `tests/test_*.py` file imports
  for `sys.path` setup and a reusable `IsolatedCwd` context manager, so
  no test run ever creates or pollutes `module_data/`/`logs/` inside the
  real repository checkout.
- Added `tests/run_tests.py` as the single entry point for the suite
  (`python tests/run_tests.py`), wrapping `unittest`'s own discovery and
  text runner. Exits `0` on success and `1` on any failure, so it can be
  used as a CI or pre-commit gate.
- Added 13 new `tests/test_*.py` modules covering, end to end:
  - `brisartos/emitter.py` (`Emitter`) and `brisartos/labels.py`
    (`Labels`) -- exact opcode/byte-level checks and relative-jump fixup
    boundary conditions (-128..127).
  - `brisartos/platform.py` and `brisartos/runtime/brisart_platform.py`
    (both `PlatformInfo` classes) -- their independent `describe()`
    contracts.
  - `brisartos/boot/make_boot_image.py` (`rel8()`, `build_boot_sector()`)
    -- including a full integration test that builds a real boot sector
    and runs it through the existing `tests/boot_sector_test.py` 8086
    emulator, asserting the captured BIOS `int 0x10` output matches the
    banner text exactly.
  - `brisartos/runtime/system_api.py` (`SystemAPI`) -- object ID
    generation, `safe_name()` sanitization (including path-traversal
    inputs), module-data read/write, and log append behavior.
  - `brisartos/runtime/module_api.py` (`ModuleAPI`) -- every
    permission-gated method individually, plus `get_service()` /
    `available_services()` behavior with and without a service registry
    attached.
  - `brisartos/services/service_registry.py` (`ServiceRegistry`,
    `ServiceRecord`) and `brisartos/services/filesystem_service.py`
    (`FilesystemService`) -- registration/lookup contracts and
    sandbox/path-containment enforcement.
  - `brisartos/runtime/module_loader.py` (`ModuleLoader`,
    `LoadedModule`) -- discovery, ABI-mismatch skipping, broken-module
    skipping without crashing the whole discovery pass, and the
    framework-level lifecycle logging that bypasses a module's own
    declared permissions.
  - `brisartos/runtime/runtime.py` (`BrisartRuntime`) -- full boot,
    module lifecycle, and service lifecycle integration tests, run
    against the real `modules/hello_lab/` module copied into an isolated
    temporary directory.
  - `brisartos/apps/browser.py` (`TextHTMLParser`, `normalize_url`,
    `fetch_page`) -- HTML-to-text extraction and URL normalization, with
    `urlopen` fully mocked so no real network call is ever made.
  - `modules/hello_lab/module.py` -- a full permission-denial matrix
    proving that removing any one of its four declared permissions
    (`log`, `module_data`, `object_id`, `service:filesystem`) fails at
    the exact call site that needed it, not somewhere unrelated.
### Notes
- No production code changed as part of this release. The suite is
  purely additive under `tests/`.
- While building this suite, two pre-existing fragility points were
  identified and documented (in the relevant test files' docstrings)
  rather than silently patched:
  - `runtime.py` imports `version.py` with a flat `from version import
    ...`, which only resolves correctly if the repository root happens
    to already be on `sys.path` -- true in normal usage only because the
    process's working directory is implicitly added. Tests add the repo
    root explicitly rather than relying on this.
  - `SystemAPI.__init__` unconditionally creates `module_data/` and
    `logs/` relative to `Path.cwd()`, with no constructor override.
    Every test that touches `SystemAPI` (directly or via
    `BrisartRuntime`) runs inside `IsolatedCwd` to avoid writing into the
    real repository checkout.
- Also identified two environment-level naming collisions that are not
  bugs in BrisartOS itself but had to be worked around in the test
  suite: (1) `brisartos/platform.py` shares a name with the Python
  standard library's own `platform` module, and (2) some Python
  environments ship an unrelated, site-installed package literally named
  `tests`, which can shadow this repository's `tests/` directory during
  package-qualified imports. Both `brisartos/platform.py` and
  `tests/boot_sector_test.py` are loaded by explicit file path under
  private aliases in `tests/_support.py` to sidestep this rather than
  relying on import order.
### Verified
- Ran the full suite via `python tests/run_tests.py`: 167 tests, 0
  failures, 0 errors.
- Re-ran the suite from a working directory other than the repository
  root (`cd /tmp && python /path/to/BrisartOS/tests/run_tests.py`) to
  confirm path resolution does not depend on the caller's own `cwd`.
- Confirmed no stray `module_data/`, `logs/`, or other artifacts are
  left behind anywhere in the repository after a full suite run.
- Simulated a clean drop-in of every new `tests/` file into a copy of
  the repository containing only the pre-existing
  `tests/boot_sector_test.py`, and confirmed the same 167/167 pass
  result with zero manual setup steps beyond copying the files.

---

## [0.9.1-alpha] - 2026-08-25

### Fixed
- Fixed two bare-metal safety bugs in `brisartos/boot/make_boot_image.py`
  that were invisible in emulation but could fail on real firmware:
  - **Uninitialized stack.** `int 0x10` requires the CPU to push
    FLAGS/CS/IP onto SS:SP. The boot sector never set up a stack, so
    on real hardware that push could land on garbage memory instead
    of a safe location. Fixed by explicitly setting SS=0, SP=0x7C00
    (stack grows down into unused low memory) before any interrupt is
    invoked, with `cli`/`sti` bracketing the setup so a stray hardware
    interrupt can't fire mid-transition.
  - **Unnormalized CS.** The BIOS boot handoff is not guaranteed to be
    CS:IP = 0000:7C00; some firmware uses 07C0:0000 instead (same
    physical address, different segment). Every absolute offset in
    this boot sector assumed the former. Fixed with a direct far jump
    (`ljmp 0x0000:<offset>`) immediately after stack setup, which pins
    CS to 0 regardless of which convention the firmware used.
  - Also added an explicit `cld` before the `lodsb` print loop, since
    the direction flag's state is not guaranteed at boot either.

### Changed
- Extended `tests/boot_sector_test.py` to support the new instructions
  this fix introduces (`cli`, `sti`, `cld`, `mov ss/sp`, far
  `jmp ptr16:16`) and to simulate a real stack: the interpreter now
  tracks SS:SP and pushes onto it exactly as a real CPU would before
  honoring an interrupt, raising a clear error if SS:SP was never
  initialized or would underflow. This means the emulator can now
  catch the exact class of bug this release fixes, instead of quietly
  accepting a boot sector that happens to work in emulation but not on
  real silicon.

### Verified
- Re-disassembled the rebuilt `build/brisartos_boot.img` with objdump
  in 16-bit real mode: `cli`, full segment/stack setup, `sti`, `cld`,
  and the far jump (`ljmp $0x0,$0x7c13`) all decode exactly as
  intended, landing precisely on the patched targets.
- Re-ran the (now stack-aware) boot sector emulator against both the
  standalone `.img` and the sector embedded in `.vfd`. Both pass: the
  stack is valid by the time `int 0x10` executes, and the correct
  banner text prints before a clean `HLT`.

### Notes
- This is a correctness/safety fix to existing boot behavior, not new
  boot sector functionality -- the sector still only prints a banner
  and halts -- so this is a patch release per the versioning policy
  above.
- Real hardware or a standard emulator (QEMU, Bochs, or a Hyper-V
  Generation 1 VM with the .vfd attached as a virtual floppy) is still
  the next verification step; this fix specifically targets failure
  modes that a custom Python interpreter can approximate but not fully
  replace.
- Corrected an incorrect file path referenced earlier in discussion of
  this emulator: `boot_sector_test.py` lives at
  `tests/boot_sector_test.py`, matching the actual repository folder
  tree -- not `brisartos/boot/boot_sector_test.py`. No code moved and
  no behavior changed; noted here rather than as a separate release
  since it's a documentation correction, not a functional change.

---

## [0.9.0-alpha] - 2026-08-25

### Added
- Added `brisartos/boot/boot_sector_test.py`: a pure-Python, dependency-free
  8086 real-mode CPU interpreter that loads a 512-byte boot image at
  physical address 0x7C00 (matching real BIOS boot behavior) and
  executes it instruction-by-instruction, including BIOS `int 0x10`
  teletype video output. Implements exactly the instruction subset the
  current boot sector uses (XOR, MOV Sreg, MOV SI/AH, LODSB, TEST, JZ,
  INT, JMP, HLT); any unsupported opcode raises a clear
  `UnsupportedInstruction` error naming the opcode and address instead
  of silently mis-executing.
- This gives BrisartOS a behavioral, offline boot sector smoke test
  with zero external tools (no QEMU, Bochs, or VM required), matching
  the project's dependency-free philosophy all the way down to
  hardware-boot verification.

### Fixed
- Removed a real bug in `brisartos/build.py`: its `build_image()`
  function wrote non-executable ASCII placeholder bytes to
  `build/brisartos_boot.img` -- the exact same path
  `brisartos/boot/make_boot_image.py` writes the real, executable
  512-byte boot sector to. Running `build.py` after
  `make_boot_image.py` silently destroyed the working bootloader with
  no warning. `build.py` is now a thin entry point that calls the one
  canonical generator in `make_boot_image.py`, so there is exactly one
  boot sector implementation in the project instead of two disagreeing
  ones.

### Verified
- Disassembled `build/brisartos_boot.img` with objdump in 16-bit
  real-mode (`-m i8086 --adjust-vma=0x7c00`): every instruction decodes
  as intended and the patched `mov si` operand lands exactly on the
  embedded message text.
- Ran the new boot sector emulator against both the standalone 512-byte
  `.img` and the sector embedded inside `build/brisartos_boot.vfd`
  (byte-identical to the standalone image). Both reach `HLT` cleanly
  and produce the correct BIOS teletype output with no infinite-loop or
  unsupported-instruction failures.

### Notes
- This is the first BrisartOS boot artifact to be behaviorally
  verified rather than only visually/statically inspected.
- Real hardware or a real emulator (QEMU, Bochs, or a Hyper-V
  Generation 1 VM with the .vfd attached as a virtual floppy) is still
  the next verification step before this touches physical media; the
  emulator here is a fast offline regression check, not a replacement
  for that.

---

## [0.8.0-alpha] - 2026-08-10

### Added
- Implemented real sandboxed file operations in FilesystemService
  (list_files, read_text, write_text, read_bytes, write_bytes,
  delete_file, exists, file_info), scoped per module under
  module_data/<module_name>/.
- Added path-containment enforcement in FilesystemService so no
  filename or path traversal attempt (e.g. "../../etc/evil.txt")
  can escape a module's own data directory.
- Wired ServiceRegistry to accept and inject module_data_root into
  FilesystemService at registration time.
- Wired BrisartRuntime to pass SystemAPI.module_data_root into
  ServiceRegistry, so SystemAPI and FilesystemService share one root.
- Updated the Hello Lab module to demonstrate the "service:filesystem"
  permission and ModuleAPI.get_service("filesystem") usage end-to-end.

### Changed
- FilesystemService version bumped from 0.1.0 to 0.2.0.
- Hello Lab module version bumped from 0.1.0 to 0.2.0.

### Notes
- This is the first built-in service with real (non-stub) behavior;
  Archive, Settings, and Update services remain stubs.
- This update completes the loop opened in 0.4.3-alpha (permission-aware
  ModuleAPI) and 0.4.4-alpha (ServiceRegistry wiring) by giving modules
  an actual, permission-gated service to call.
- Verified functionally: boot, service listing, module execution, file
  read/write through both module_data and the filesystem service,
  sandbox-escape rejection, and permission enforcement (PermissionError
  and ServiceUnavailableError) all tested and passing.

---

## [0.7.0-alpha] - 2026-08-10

### Added
- Added ServiceRegistry wiring through ModuleLoader into ModuleAPI.
- Added ModuleAPI.get_service(name), gated by "service:<name>" permission.
- Added ServiceRegistry.get_service_object() and has_service() accessors.
### Changed
- Modules can now request live service instances instead of only SystemAPI primitives.
### Notes
- Built-in services remain stubs; real service logic is the next step.

---

## [0.6.0-alpha] - 2026-08-10

### Added
- Added permission-aware module API wrapper.
- Added runtime enforcement for module permissions.
- Added explicit `object_id` permission for modules that generate BrisartOS object identifiers.
- Added module permission display to module inspection output.

### Changed
- Modules now receive a permissioned API wrapper instead of the unrestricted core SystemAPI object.
- The Hello Lab module now declares its object identifier permission explicitly.

### Notes
- This update turns module metadata into an enforceable runtime contract.
- This keeps BrisartOS dependency-free and standard-library-only.
- This advances the module API and shell inspection roadmap.

---

## [0.5.0-alpha] - 2026-08-10

### Added
- Added a BrisartOS service registry for built-in operating environment services.
- Added runtime registration for archive, filesystem, settings, and update services.
- Added `services` shell command to list registered services and their current status.
- Added `service <name>` shell command to inspect an individual service.
- Added a dedicated `ServiceRecord` wrapper for service metadata and status reporting.

### Changed
- Runtime boot now initializes the service layer before module discovery.
- Shell help output now includes service inspection commands.

### Notes
- This update keeps BrisartOS dependency-free and standard-library-only.
- Existing service classes remain simple and unchanged.
- This update advances the short-term roadmap goal of wiring the service framework into the runtime.

---

## [0.4.1-alpha] - 2026-08-07

### Changed
- Centralized the BrisartOS version into a single source of truth (`brisartos/version.py`).
- `runtime.py` now imports NAME and VERSION from `version.py` instead of hardcoding.
- `build.py` boot banner now derives its version from `version.py`, fixing the stale `0.2.0-alpha` string (now `0.4.0-alpha`).

### Fixed
- Resolved version mismatch between the runtime (`0.4.0-alpha`) and the build boot banner (`0.2.0-alpha`).