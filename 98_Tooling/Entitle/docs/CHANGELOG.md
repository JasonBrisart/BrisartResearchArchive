# Changelog
All notable changes to Entitle are documented in this file.
Entitle is pure Python with no external dependencies and is designed for
local-first, offline, and air-gapped environments.

---

## [0.4.1] - 2026-09-10

An architecture-consistency release. Every `__init__.py` file in the project
has been removed; `entitle`, `entitle/tracking`, `gui`, and `gui/tabs` are now
PEP 420 implicit namespace packages, matching the convention already used
elsewhere in the Brisart ecosystem. No entitlement format, BSR2 protection
logic, or CLI/GUI behavior changed. If you only run `main.py`
`issue`/`verify`/`track`/`revoke`/`report`/`gui`, nothing about how you invoke
Entitle changes in this release.

### Removed

- **`entitle/__init__.py`** — previously re-exported `__version__` (itself
  read from the root `version.py`) and inserted the repository root onto
  `sys.path`. Every real entry point (`main.py`, `gui/app.py`,
  `examples/protected_app_example.py`, `tests/conftest.py`) already performed
  its own `sys.path` setup independently, so the file's only functional
  purpose had become exposing `entitle.__version__` — which nothing besides
  one test relied on. Removed with no functional loss.
- **`entitle/tracking/__init__.py`** — previously re-exported
  `count_deployments`, `register_deployment`, `deploy_from_file`,
  `record_fork`, `record_provenance`, and `list_records` from the tracking
  submodules. `entitle/tracking/cli.py` already imported directly from the
  submodules (`.deploy`, `.fork`, `.provenance`, `.query`); only the GUI's
  Deploy and Fork/Provenance tabs, and two test files, used the package-level
  re-export.
- **`gui/__init__.py`** and **`gui/tabs/__init__.py`** — both contained only a
  module docstring with no functional code; nothing imported from either at
  the package level.

### Changed

- **`gui/tabs/deploy_tab.py`** now imports `deploy_from_file` from
  `entitle.tracking.deploy` directly, instead of from the removed
  `entitle.tracking` package-level re-export.
- **`gui/tabs/fork_provenance_tab.py`** now imports `record_fork` from
  `entitle.tracking.fork` and `record_provenance` from
  `entitle.tracking.provenance` directly, instead of from `entitle.tracking`.
- **`tests/test_report.py`** and **`tests/test_tracking.py`** updated the same
  way: `record_fork`, `register_deployment`, `record_provenance`, and
  `list_records` are now imported from their owning submodules
  (`entitle.tracking.deploy`, `entitle.tracking.fork`,
  `entitle.tracking.provenance`, `entitle.tracking.query`).
- **`tests/test_paths.py`**'s version-parity test no longer does
  `from entitle import __version__`, since that only worked through the now-
  removed `entitle/__init__.py`. It now confirms the root `version.py`'s
  `__version__` is a well-formed string directly — `main.py`, the GUI, and
  this test all already read the version the same way (`from version import
  __version__`), so there was never a second version value to stay in sync
  with.

### Verified

- Confirmed by direct interpreter inspection that `entitle`, `entitle.tracking`,
  `gui`, and `gui.tabs` are genuine PEP 420 namespace packages after removal
  (`__file__` is `None`; `__path__` correctly resolves to each directory).
- Full test suite re-run with zero `__init__.py` files anywhere in the tree:
  82 tests pass, unchanged from 0.4.1.
- Full CLI lifecycle (issue, verify, track deploy, revoke, report) re-run
  end-to-end through `main.py` with identical results to 0.4.1.
- `tests/test_bsr_integrity.py` re-confirmed: the four vendored BSR2 files are
  untouched by this change and still match their pinned SHA-256 values.

### Notes

- This release contains no changes to the entitlement payload format, the
  BSR2 envelope protocol, the tamper-evident record format, or any CLI/GUI
  command or workflow behavior.
- If you have code that does `from entitle import __version__` or
  `from entitle.tracking import <function>` directly, update it to
  `from version import __version__` and
  `from entitle.tracking.<deploy|fork|provenance|query> import <function>`
  respectively. All function signatures and behavior are unchanged.
- No new external dependencies were introduced; the project remains pure
  Python, standard-library only.

---

## [0.4.0] - 2026-09-10

An architecture and consistency release, not a behavior release. This entry
covers a full internal reorganization of the project layout, naming, and
runtime-data hygiene brought up to parity with the rest of the Brisart
ecosystem. No entitlement format changed, no BSR2 protection logic changed,
and every existing CLI command still does exactly what it did in 0.3.x. If
you only use `main.py issue/verify/track/revoke/report`, nothing about how
you invoke Entitle changes in this release.

### Changed

- **Renamed `bsr/` to `vendor/`.** This is the same directory containing the
  four unmodified BrisartSecurityResearch (BSR2) modules; only the folder
  name changed, to match the naming convention used across the rest of the
  Brisart ecosystem. `entitle/bootstrap.py`'s `VENDOR_DIR` now points at the
  renamed directory.
- **Moved the version string to a root-level `version.py`.** Previously
  `__version__` lived inside `entitle/__init__.py`. It now lives in a
  standalone `version.py` at the repository root, which `entitle/__init__.py`
  and `main.py --version` both import from, so the package, the CLI, and any
  future packaging or release tooling read the version from exactly one
  place.
- **Renamed `entitle/constants.py` to `entitle/record_types.py`.** The module
  only ever held the five `record_type` string constants; the new name
  documents that directly.
- **Split `entitle/track.py` into an `entitle/tracking/` package.** The
  276-line module previously mixed governed deployment recording (which
  checks entitlement rights, deployment limits, and revocation status)
  together with purely documentary fork and provenance recording. It is now:
  - `tracking/deploy.py` — `register_deployment()`, `deploy_from_file()`,
    `count_deployments()`
  - `tracking/fork.py` — `record_fork()`
  - `tracking/provenance.py` — `record_provenance()`
  - `tracking/query.py` — `list_records()`
  - `tracking/cli.py` — the `track` subcommand group (`deploy`, `fork`,
    `provenance`, `list`), dispatched from `main.py`

  `tracking/__init__.py` re-exports every public function, so existing code
  only needs to change `from entitle.track import ...` to
  `from entitle.tracking import ...` — no function signatures changed.
- **Added `entitle/paths.py`** as the single source of truth for default
  runtime-data locations (`entitlements/`, `records/`, `reports/`) used to
  pre-populate GUI fields. These defaults were previously duplicated as
  literal path strings across several `gui/tabs/*.py` modules; a change to
  one no longer risks drifting from the others. The CLI is unaffected: it
  still requires an explicit `--store` on every command, by design.
- **`gui/` and `gui/tabs/` are now explicit packages** (added `__init__.py`
  to each), matching the rest of the project instead of relying on implicit
  namespace-package behavior.

### Fixed

- **`.gitignore` did not exclude Entitle's own runtime-data directories.**
  `entitlements/`, `records/`, and `reports/` — which hold issued entitlement
  envelopes and the tamper-evident deployment/fork/provenance/revocation log
  — were previously stageable and could have been committed the first time
  the tool was run inside the repository. All three directories are now
  explicitly ignored.
- **Nothing enforced the "BSR2 is vendored byte-for-byte unmodified" claim.**
  The changelog and documentation have always asserted this, but no test
  verified it. Added `tests/test_bsr_integrity.py`, which pins the SHA-256 of
  each of the four `vendor/brisart_security_*.py` files and fails CI if any
  of them drift from the pinned hash, and fails if an unexpected fifth
  `brisart_security_*.py` file appears in `vendor/` without a corresponding
  pinned entry.
- **Record entries had no schema version marker.** The entitlement *payload*
  already carried `"format": "entitle.entitlement.v1"`, but individual
  entries appended to the tamper-evident record log had no equivalent field.
  Every record written by `RecordStore.append()` now includes
  `"format": "entitle.record.v1"` inside the hashed region, so the on-disk
  record schema can be evolved in the future while still being able to
  recognize records written by this release.

### Added

- **CI matrix expanded to `ubuntu-latest`, `windows-latest`, and
  `macos-latest`** (previously Ubuntu only), each against Python 3.10-3.12.
  CI now also runs a full CLI lifecycle smoke test — issue, verify, track
  deploy, revoke, report — against a live entitlement on every run, not just
  the unit test suite.
- **`tests/test_paths.py`** covering the new `entitle/paths.py` defaults and
  confirming `entitle.__version__` matches the root `version.py` value.
- 11 new regression tests overall (71 → 82), covering the record format
  marker, the vendor integrity pins, and the new paths module.

### Notes

- This release contains no changes to the entitlement payload format
  (`entitle.entitlement.v1`), the BSR2 envelope protocol, or any encryption,
  authentication, or context-binding logic. Entitlements issued under 0.3.x
  verify unchanged under 0.4.0.
- If you have existing scripts or code importing `entitle.track` or
  `entitle.constants` directly, update those imports to `entitle.tracking`
  and `entitle.record_types` respectively; the functions and constants
  themselves are unchanged.
- No new external dependencies were introduced; the project remains pure
  Python, standard-library only.

---

## [0.3.2] - 2026-08-26

### Changed
- Removed the unused `from pathlib import Path` import from `gui/tabs/issue_tab.py`.

### Notes
- This is a cosmetic code cleanup release only.
- No functional behavior, entitlement processing, licensing logic, CLI commands, GUI workflows, file formats, or outputs were changed.
- Improves code cleanliness and reduces dead imports in the Issue tab implementation.

---

## [0.3.1] - 2026-08-18
This release is a follow-up architecture cleanup pass on top of 0.3.0's
package restructure. No governance logic, record-store semantics, or
entitlement behavior changed.

### Added
- `entitle/constants.py` — single source of truth for the five
  `record_type` strings (`deployment`, `fork`, `provenance`, `revocation`,
  `reinstatement`) used throughout the tamper-evident record store. These
  were previously duplicated as plain string literals across
  `entitle/track.py`, `entitle/revoke.py`, and `entitle/report.py`.
- `gui/widgets.py` — the shared `FormFrame` label/entry/checkbox helper used
  by every GUI tab, extracted out of the former single-file GUI.
- `gui/tabs/` — the GUI's six tabs (Issue, Verify, Deploy, Fork /
  Provenance, Revoke / Reinstate, Audit Report) are now individual plug-in
  modules (`gui/tabs/issue_tab.py`, `verify_tab.py`, `deploy_tab.py`,
  `fork_provenance_tab.py`, `revoke_tab.py`, `report_tab.py`), each exposing
  a `TAB_TITLE` string and a `build(parent, app)` function. `gui/app.py`
  now only builds the main window and loads tabs from an explicit
  `TAB_MODULES` registry — it has no per-tab logic of its own. Adding a new
  tab means adding one new file plus one line in `TAB_MODULES`; no other
  file needs to change.

### Changed
- `gui/app.py` reduced from a single 407-line file containing all six tabs
  to a 110-line core engine that only builds the window, the shared output
  pane, and the tab registry.
- `entitle/track.py`, `entitle/revoke.py`, and `entitle/report.py` now
  import their `record_type` strings from `entitle/constants.py` instead of
  repeating literal strings, so a typo in a record type now fails at import
  time (`ImportError`/`NameError`) instead of silently matching nothing.
- `main.py`'s command dispatch replaced an `if`/`elif` chain with a
  `COMMAND_MODULES` dict mapping command name to dotted module path. Adding
  a new top-level CLI command (beyond `issue`/`verify`/`track`/`revoke`/
  `report`/`gui`) now means adding one dict entry instead of another
  `elif` branch.

### Verified
- The full CLI lifecycle (issue, verify, deploy with `deployment_limit`
  enforcement and refusal, fork, provenance, revoke, deploy-while-revoked
  refusal, reinstate, check, audit report) was re-run end-to-end through
  `main.py` after the constants and dispatch-table changes, with identical
  results to 0.3.0.
- The modularized GUI was re-verified with the same headless test harness
  used for 0.3.0: instantiate the real `EntitleApp`, confirm all six
  registered tab plug-ins appear in the notebook, and click through every
  tab's button (issue → verify → deploy ×2 → 3rd deploy refused → fork →
  provenance → revoke → deploy-while-revoked refused → reinstate → check →
  report). All 11 assertions passed against the real backend. As before,
  actual on-screen rendering should be confirmed on a machine with a
  working Tkinter/Tk installation.

---

## [0.3.0] - 2026-08-18
This release restructures Entitle from a flat collection of scripts into a
proper package with a single command-line entry point, and adds a first
Tkinter GUI covering every core workflow. No governance logic, record-store
semantics, or entitlement behavior changed — this is an architecture and
usability release, not a behavior release.

### Added
- `main.py` — single CLI entry point. Replaces running each `entitle_*.py`
  script directly. Dispatches to `issue`, `verify`, `track`, `revoke`,
  `report`, and `gui` subcommands, e.g. `python main.py issue ...`,
  `python main.py track deploy ...`.
- `entitle/` — Entitle's own logic, reorganized into a proper Python
  package (`core.py`, `records.py`, `bsr_adapter.py`, `issue.py`,
  `verify.py`, `track.py`, `revoke.py`, `report.py`, `bootstrap.py`).
  Internal imports were converted from flat (`from entitle_core import ...`)
  to package-relative (`from .core import ...`).
- `entitle/bootstrap.py` — adds the sibling `bsr/` directory to `sys.path`
  so BrisartSecurityResearch's flat, top-level imports
  (`from brisart_security_primitives import ...`) resolve correctly from
  its new subdirectory location, without modifying a single line of BSR2.
  Every entry point (CLI, GUI, example) calls this before importing
  `entitle.bsr_adapter`.
- `bsr/` — BrisartSecurityResearch (BSR2) now lives in its own directory.
  The four `.py` files are byte-for-byte unchanged from the flat layout;
  only their location moved.
- Business logic extracted from CLI argument parsing in every `entitle/`
  module, e.g. `issue_entitlement(...)`, `verify_entitlement(...)`,
  `deploy_from_file(...)`, `record_fork(...)`, `record_provenance(...)`,
  `build_report_for_path(...)`. Each CLI subcommand is now a thin wrapper
  around a plain function with the same name and keyword arguments the GUI
  calls directly — the CLI and GUI can never drift out of sync with each
  other because they share one implementation.
- `gui/app.py` — a first Tkinter GUI. Tabs for Issue, Verify, Deploy,
  Fork / Provenance, Revoke / Reinstate / Check, and Audit Report. Every
  button calls directly into the same `entitle.*` functions used by the
  CLI. Requires only the Python standard library. Launch with
  `python main.py gui` or `python gui/app.py`.
- `examples/protected_app_example.py` — moved into its own directory,
  updated for the new package layout, and hardened to print a friendly
  message with a working example command when the demo entitlement file is
  missing, instead of crashing with an uncaught `FileNotFoundError`.

### Changed
- `protected_app_example.py` → `examples/protected_app_example.py`.
- Running an Entitle module directly as a script (e.g.
  `python entitle/issue.py`) is no longer supported, because its imports
  are now package-relative. Use `python main.py issue ...` (or
  `python -m entitle.issue ...`) instead.

### Verified
- The full lifecycle (issue, verify, deploy with `deployment_limit`
  enforcement and refusal, fork, provenance, revoke, deploy-while-revoked
  refusal, reinstate, check, audit report, hash-chain tamper detection) was
  re-run end-to-end through `main.py` in a clean directory with identical
  results to the pre-restructure flat layout.
- Every function the GUI calls was cross-checked against the real
  `entitle.*` function signatures with `inspect.signature`, and the GUI's
  button callbacks were exercised end-to-end against the real backend
  (issue → verify → deploy ×2 → 3rd deploy refused → fork → provenance →
  revoke → deploy-while-revoked refused → reinstate → check → report) using
  a headless test harness, since this development environment has no
  `_tkinter` extension available to open a real window. The GUI's actual
  on-screen rendering should be confirmed on a machine with a working
  Tkinter/Tk installation (standard on Windows, macOS, and most Linux
  desktop distributions) before relying on it day-to-day.
- BSR2's four `.py` files were confirmed byte-for-byte identical (SHA-256)
  before and after the move into `bsr/`.

### Notes
- No changes were made to any BrisartSecurityResearch (BSR2) source file.
  BSR2 remains an independent, experimental research dependency and should
  continue to be treated as controlled-environment protection unless
  independently reviewed.
- Runtime data directories (`entitlements/`, `records/`, `reports/`) keep
  their previous meaning and location at the repository root; no default
  store path was introduced, preserving the existing "operator always
  specifies `--store` explicitly" design principle.

---

## [0.2.1] - 2026-08-18
This release fixes integration bugs between `entitle_bsr_adapter.py` and the
real BrisartSecurityResearch (BSR2) module that prevented `entitle_issue.py`
from running at all against an unmodified BSR2 checkout. No governance logic,
record-store behavior, or entitlement semantics changed; every fix is
isolated to the BSR2 adapter wiring layer.

### Fixed
- `entitle_bsr_adapter.py` imported `BrisartSecurityDRBG`, `encrypt_envelope`,
  and `decrypt_envelope`, but the real BSR2 module exports `BrisartDRBG`,
  `encrypt`, and `decrypt`. Import aliasing was added so BSR2 source files
  can be used completely unmodified.
- `protect_entitlement_payload()` called BSR2's `encrypt()` with a `drbg=`
  keyword argument, but BSR2 names that parameter `rng`. Calls were updated
  to `rng=drbg`.
- `make_context()` returned `bytes`, but BSR2's `encrypt()` and `decrypt()`
  both require `context` to be a `str`. `make_context()` now returns a
  string.
- Confirmed the README's suggested `bsr/` subfolder layout does not work as
  written: BSR2's own modules (`brisart_security_drbg.py`,
  `brisart_security_envelope.py`) use flat imports
  (`from brisart_security_primitives import ...`) that cannot resolve from
  inside a subpackage without modifying BSR2 itself. Documented that BSR2
  source files must be placed flat, beside the Entitle source files,
  completely unmodified. (Superseded in 0.3.0 by
  `entitle.bootstrap.ensure_bsr_on_path()`, which adds `bsr/` to `sys.path`
  directly so the flat layout can live in its own subdirectory.)

### Verified
- Every known-answer vector shipped with BrisartSecurityResearch (hash, MAC,
  stream, DRBG output, envelope decrypt, and a deterministic envelope
  re-encrypt) was reproduced byte-for-byte against the unmodified BSR2
  source, confirming the cryptographic primitive layer was untouched and
  correct throughout.
- The full lifecycle was exercised end-to-end in a clean environment:
  issue, verify, governed deploy (including `deployment_limit` enforcement
  and refusal), fork, provenance, revoke, reinstate, and audit reporting.
- Hash-chain tamper detection was confirmed directly: a manually corrupted
  historical record was correctly flagged by `verify_chain()`, with the
  exact broken record index reported.

### Notes
- No changes were required to `entitle_core.py`, `entitle_records.py`,
  `entitle_track.py`, `entitle_revoke.py`, or `entitle_report.py`; all
  governance and tamper-evidence logic in those modules was already correct.
- BrisartSecurityResearch (BSR2) source itself was not modified in any way.
  BSR2 remains an independent, experimental research dependency and should
  continue to be treated as controlled-environment protection unless
  independently reviewed.

---

## [0.2.0] - 2026-08-04
This release brings the implementation in line with the README by adding the
deployment, fork, provenance, revocation, and audit capabilities that were
previously described but not yet built. All new tooling is pure standard
library and writes to a single local, tamper-evident record store.

### Added
- `entitle_records.py` — append-only, hash-chained record store. Each entry is
  linked to the previous one through a SHA-256 chain, so any edit, deletion, or
  reordering of earlier records is detectable via `verify_chain()`.
- `entitle_track.py` — record deployments, internal forks, and provenance /
  ownership to the shared store. Includes `deploy`, `fork`, `provenance`, and
  `list` subcommands.
- Governed deployments: `register_deployment` only records a deployment when the
  entitlement verifies, grants `can_run`, is not revoked, and its
  `deployment_limit` has not been reached.
- `entitle_revoke.py` — offline revocation with `revoke`, `reinstate`, and
  `check` subcommands. Revocation status is derived from the record log, so an
  entitlement can be revoked and later reinstated while preserving full history.
- `entitle_report.py` — audit and reporting over the record store, with text or
  JSON output. Summarizes records by type and deployments by product, and
  verifies the tamper-evident hash chain across the whole store.

### Changed
- `entitle_track.py` deployment gate now consults `entitle_revoke.is_revoked`
  before recording, so revoked entitlements are refused for new deployments.
- `README.md` rewritten to document the actual tools with runnable CLI examples,
  and to add Requirements, Project Layout, Deployment Tracking rules, Revocation
  & Reinstatement, and the Tamper-Evident Record Store.

### Removed
- Dropped the unimplemented **License Management** feature section from the
  README so documentation matches shipped functionality.

### Notes
- The record store path is always explicit (`--store`); there is no default
  location by design, keeping record placement fully under operator control.
- Entitlement protection continues to rely on the experimental
  BrisartSecurityResearch (BSR) modules via `entitle_bsr_adapter.py`. Treat as
  controlled-environment protection unless independently reviewed.
