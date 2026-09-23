All notable changes to BrisartOS are documented in this file.

BrisartOS is a pure-Python, dependency-free, fully custom operating
system research project.

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