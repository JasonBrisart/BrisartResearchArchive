# Known Issues

This file tracks open issues in BrisartIdentityTools: defects, and limitations
that still have a next step. Each entry uses the same bug-report template,
modeled on GitHub Issues and Jira, so severity, scope, and next steps are easy
to compare.

Limits of the design itself are not tracked here: BSR2 being unreviewed,
metadata that stays readable while a store is locked, a leaked master key that
can't be taken back, and similar. They are listed, each with what you can do
about it, in
[What these tools do not protect against](BSR2_INTEGRATION.md#what-these-tools-do-not-protect-against).

Fixed issues move to **Resolved** at the bottom of this file, so the open list
shows only what is still outstanding.

---

## Open issues at a glance

| ID | Issue | Severity | Status |
| --- | --- | --- | --- |
| [KI-001](#ki-001-video-liveness-threshold-is-uncalibrated-against-real-camera-hardware) | Video liveness threshold is uncalibrated against real camera hardware | Medium | Open: needs real-camera samples |
| [KI-003](#ki-003-bulk-processing-is-constrained-by-throughput-memory-and-temporary-storage) | Bulk processing is constrained by throughput, memory, and temporary storage | Low | Documented limitation |
| [KI-005](#ki-005-existing-record-metadata-changes-can-break-payload-authentication) | Existing-record metadata changes can break payload authentication | Medium | Open |
| [KI-006](#ki-006-biometrics-bulk-cli-and-direct-bulk-apis-do-not-validate-chunk-size) | Biometrics bulk CLI and direct bulk APIs do not validate chunk size | Medium | Open |
| [KI-007](#ki-007-biometrics-gui-can-hide-legitimate-attachment-names) | Biometrics GUI can hide legitimate attachment names | Medium | Open |

Resolved issues are listed at the end of this file.

To report a new problem, use the [template](#template) and paste the output
of `python tools/envinfo.py` into its **Environment** field. Security problems
are reported privately instead; see [SECURITY.md](SECURITY.md).

---

## KI-001: Video liveness threshold is uncalibrated against real camera hardware

- **Reported date:** 2026-09-03
- **Severity:** Medium
- **Environment:** All platforms; affects the `video` biometric modality only.
- **Component:** `biometrics/features/liveness.py`,
  `biometrics/engine/enrollment.py`, `biometrics/engine/verification.py`
- **Steps to Reproduce:**
  1. Enroll or verify a `video` modality probe recorded from a real camera
     rather than the project's synthetic sample generator.
  2. Observe the `motion_energy` value reported in the liveness result.
- **Expected behavior:** `DEFAULT_LIVENESS_THRESHOLD` (0.75) should reliably
  separate a genuinely static clip from a live capture across real hardware,
  lighting, and sensor noise conditions.
- **Actual behavior:** The threshold has only been validated against this
  project's own synthetic sample generator
  (`biometrics/samples/sample_generator.py`), which is a much cleaner signal
  than a real camera. It is unknown whether 0.75 produces false rejections
  (genuine live captures with low sensor noise) or false acceptances (a wobbled
  photo) on real hardware.
- **Tried / Ruled out:** The gate itself (motion-presence detection via
  mean absolute frame-to-frame pixel difference) is unit-tested and correct
  against hand-built static and moving frame sequences — see
  `biometrics/tests/test_liveness.py`. The gap is calibration data, not logic.
- **Next step:** Collect real-camera liveness samples (live captures vs.
  static photo replays) across a few devices, measure `motion_energy` on
  each, and re-tune `DEFAULT_LIVENESS_THRESHOLD` (or make it configurable
  per deployment) once real data exists.

---

## KI-003: Bulk processing is constrained by throughput, memory, and temporary storage

- **Reported date:** 2026-08-25
- **Severity:** Low for the documented performance limitation; deployment
  impact depends on bundle size and available resources.
- **Environment:** All platforms; Vault bulk bundles and Biometrics bulk
  attachments.
- **Component:** `vault/store/bulk_file_service.py`,
  `biometrics/engine/bulk_attachments.py`
- **Steps to Reproduce:**
  1. Select a representative file or directory tree.
  2. Run `encrypt-paths` or `attach-paths`.
  3. Observe elapsed processing, memory use, temporary storage, and skipped
     files.
  4. Restore the resulting bundle and observe the same resource requirements.
- **Expected behavior:** Chunking stores large content as several sealed
  records plus a manifest. It does not promise unlimited-size or
  bounded-memory processing.
- **Actual behavior:** Path bundles are materialized as plaintext temporary
  ZIP files and read completely into memory. Restore reassembles complete
  content before extraction. Earlier development documentation reports small
  sample rates around 1.4 KB/s, but those measurements are not guaranteed
  sustained throughput on another machine. Large operations can exhaust
  memory or disk space, and unreadable source files can be skipped.
- **Tried / Ruled out:** Regression tests exist for file and bundle round trips
  in `vault/tests/test_bulk_file_service.py`,
  `vault/tests/test_file_records.py`,
  `biometrics/tests/test_bulk_attachments.py`, and
  `biometrics/tests/test_attachments.py`. Their presence does not establish
  full-drive backup correctness, unlimited-size processing, or crash recovery.
- **Next step:** Measure representative deployment data and document resource
  requirements. A bounded-memory implementation would require an explicit
  streaming redesign. Keep independent backups until restore results have
  been checked. See [file and bundle encryption](FILE_AND_BUNDLE_ENCRYPTION.md).

---

## KI-005: Existing-record metadata changes can break payload authentication

- **Reported date:** 2026-11-08
- **Severity:** Medium (correctness)
- **Environment:** LTS-2028 1.3.x, LTS-2028 1.4.x, and Official; all
  platforms.
- **Component:** `vault/store/vault_service.py`
- **Steps to Reproduce:**
  1. Create a record with `vault upsert`.
  2. Run `vault upsert` again with `--record-id` set to that record's id and a
     different label or `--kind`.
  3. Read the record with `vault get`.
- **Expected behavior:** The update stores the new payload, label, and kind
  together, and the record reads back.
- **Actual behavior:** The payload is sealed under a context built from the
  new label and kind, but the record keeps its old label and kind. Reading it
  rebuilds the context from the stored, old values, so the payload fails
  authentication.
- **Tried / Ruled out:** Reproduced with a temporary vault and an injected test
  key; no real user data was used.
- **Next step:** Fix the update path in a code change. Until then, keep a
  record's label and kind unchanged when reusing its id. Encryption migration
  leaves a record in this state as it is and reports it.

---

## KI-006: Biometrics bulk CLI and direct bulk APIs do not validate chunk size

- **Reported date:** 2026-11-08
- **Severity:** Medium (correctness)
- **Environment:** LTS-2028 1.3.x, LTS-2028 1.4.x, and Official; all
  platforms. Direct API callers, and `biometrics attach-paths --chunk-mb`,
  which passes its value through unchecked. `vault encrypt-paths` accepts
  only 1 to 15.
- **Component:** `vault/store/bulk_file_service.py`,
  `biometrics/engine/bulk_attachments.py`
- **Steps to Reproduce:**
  1. Construct `BulkFileService` with `chunk_bytes=0`, or call
     `attach_large_bytes()` with `chunk_bytes=0`, or run
     `python cli.py biometrics attach-paths <id> <name> <path> --chunk-mb 0`.
  2. Store nonempty bytes.
  3. Repeat with a negative size.
- **Expected behavior:** An invalid chunk size is rejected with a clear error
  before anything is processed.
- **Actual behavior:** Zero raises a bare `ValueError` from `range()`. A
  negative size produces no chunks at all.
- **Tried / Ruled out:** Reproduced through the chunk iterator. The
  constructor, the API functions, and the biometrics CLI were inspected and do
  not validate the size.
- **Next step:** Validate the size in a code change. Until then, use the
  default `--chunk-mb`, and direct callers must pass a positive integer.

---

## KI-007: Biometrics GUI can hide legitimate attachment names

- **Reported date:** 2026-11-08
- **Severity:** Medium (correctness)
- **Environment:** LTS-2028 1.3.x, LTS-2028 1.4.x, and Official; all
  platforms. Desktop interface only; `biometrics inspect` lists every
  attachment entry.
- **Component:** `gui/tabs/tab_biometrics.py`
- **Steps to Reproduce:**
  1. Attach a file whose name contains `.chunk`, for example
     `notes.chunked.txt`.
  2. Refresh the attachment list in the Biometrics tab.
- **Expected behavior:** Only the internal `<name>.chunkN` entries of bulk
  attachments are hidden.
- **Actual behavior:** The list hides every name containing `.chunk`, so the
  attachment is missing from the list. It is still stored.
- **Tried / Ruled out:** Confirmed by reading the filename filter; not
  reproduced by clicking through a real display.
- **Next step:** Match only the internal chunk-name pattern in a code change.
  Until then, avoid `.chunk` in attachment names.

---

## Template

Use this template for new entries:

```markdown
## KI-XXX: <short title>

- **Reported date:** YYYY-MM-DD
- **Severity:** Critical / High / Medium / Low
- **Environment:** <output of `python tools/envinfo.py`, plus the affected
  line, tool, and modality>
- **Component:** <file(s) or module(s)>
- **Steps to Reproduce:**
  1. ...
- **Expected behavior:** ...
- **Actual behavior:** ...
- **Tried / Ruled out:** ...
- **Next step:** ...
```

---

## Resolved

Closed issues are kept here (rather than deleted) so there is a durable
record of what used to be broken and how/when it was fixed. Each entry keeps
its original fields, with **Next step** replaced by **Resolved date** and
**Resolution** once the fix has actually landed.

### KI-002: GUI had no automated test coverage — RESOLVED

- **Reported date:** 2026-09-04
- **Severity:** Low
- **Environment:** All platforms; affects `gui/` only (CLI and application
  layers are unaffected and already covered by `biometrics/tests/`,
  `vault/tests/`, `packages/tests/`, `crypto/tests/`, `common/tests/`).
- **Component:** `gui/core/`, `gui/widgets/`, `gui/tabs/`
- **Steps to Reproduce:** Run `python tests/run_tests.py` before this issue
  was addressed; no test files existed under any `gui/` subdirectory.
- **Expected behavior:** Every application layer that other tools' tests
  hold to a professional bar should have at least baseline regression
  coverage, consistent with the rest of the repository's test discipline.
- **Actual behavior:** `gui/` was the one subsystem with zero test files,
  meaning a regression in the repo-root bootstrap logic, the background
  worker/queue mechanism, the path-selection panel's dedup logic, or any of
  the three tab modules' own selection/list/refresh logic could ship
  silently.
- **Tried / Ruled out:** N/A — this was a coverage gap, not a defect.
- **Resolved date:** 2026-09-07
- **Resolution:** Full baseline coverage added under `gui/tests/`, in two
  passes:
  1. `test_constants.py`, `test_busy.py`, `test_path_panel.py` — covering
     the repo-root bootstrap walk, the background-thread/queue contract in
     `run_in_background`, and `PathSelectionPanel`'s path add/dedup/
     remove/clear logic.
  2. `test_tab_vault.py`, `test_tab_biometrics.py`, `test_tab_packages.py`
     — covering the three `gui/tabs/*.py` modules directly: record/
     identity/recipient selection helpers, the Records-vs-Files kind
     filtering in `VaultTab`, the manifest/chunk display-name logic in
     `BiometricsTab`'s attachment list, and `PackagesTab`'s master-key
     derivation and recipient-list refresh.

  All six files use a `_HAS_DISPLAY` skip guard: they run for real on a
  machine with a working Tk display and skip cleanly on a headless CI
  runner with no display. Coverage is intentionally scoped to
  state-inspection and list-refresh logic; methods that pop a real modal
  dialog or run a background KDF-touching operation (`_ensure_keyring`,
  `_enroll`, `_verify`, `_create_package`, `_run_demo`, and similar) are not
  exercised, since no user is present in an automated run to dismiss a
  blocking dialog. Full click-through workflow simulation remains a
  possible future addition but is not required for this issue to be
  considered resolved.
