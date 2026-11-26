# Changelog

## 1.10.4 - 2026-11-26

### Changed
- `crypto/encryption.py`: Resolve BSR2 from archive-root `97_Encryption/v4`, replacing `97_Encryption/Official`. Preserve the existing fail-closed validation and module-origin checks.
- `crypto/tests/test_encryption_link.py`: Update the expected dependency location for the installed layout.
- `version.py`: Increment the patch release version.

### Compatibility
- Required layout: `BrisartResearchArchive/97_Encryption/v4` and `BrisartResearchArchive/98_Tooling/Identity_Tools/Official`.
- Existing encryption formats and stored records are unchanged; `97_Encryption` was not modified.
- Linux dependency tests are run against the exported source; Windows startup is not verified.


All notable changes to BrisartIdentityTools are recorded here.

---

## [1.10.3] - 2026-11-23

A correctness release for bulk encryption and bulk biometric attachments. Bulk
operations now reject chunk sizes that are not positive integers, and
`biometrics attach-paths` validates `--chunk-mb` before loading the keyring or
asking for a passphrase. This closes KI-006.

The correction originated in LTS-2028 1.3.13 and was forward-ported to Official
with the same implementation and regression coverage. LTS-2028 1.4.3 receives
the same correction. LTS-2028 1.3.x continues to use its vendored BSR2 Alpha 3
implementation and retains its line-specific documentation concerning the
envelope payload limit.

This was a data-integrity defect rather than a confidentiality defect. No data
was disclosed. However, a negative chunk size could make a bulk operation report
success after storing a manifest with no data chunks, leaving the content
unrecoverable from that bundle.

### Fixed

- **Bulk file encryption and bulk biometric attachments now reject invalid
  chunk sizes.** `BulkFileService`, `attach_large_bytes()`, and
  `attach_paths()` previously passed `chunk_bytes` directly to the chunk
  iterator, which calls `range(0, len(data), chunk_size)`. No validation
  occurred before that call.

  The previous behavior depended on the supplied value:

  - A chunk size of `0` raised the bare exception
    `ValueError: range() arg 3 must not be zero`.
  - A negative integer reported success after writing a manifest with
    `chunk_count` set to `0` and no data chunks. Restoration later failed
    because the reassembled size was `0` instead of the size recorded in the
    manifest.
  - A float such as `1.5` or a string such as `"8"` raised a bare `TypeError`
    from `range()`.
  - `True` was accepted as a one-byte chunk size because `bool` inherits from
    `int`. An 11-byte input therefore produced 11 sealed records.

  Each bulk module now owns a small `_validate_chunk_bytes()` helper. The
  helper accepts only a positive `int` and explicitly rejects `bool`. Invalid
  values raise the error belonging to the affected module:
  `BulkFileServiceError` for Vault bulk operations or `BulkAttachmentError`
  for Biometrics bulk attachments. Both errors inherit from `ValueError`.

  The validation helpers remain duplicated intentionally, following the
  existing `_unique_arcname()` ownership pattern. Vault and Biometrics
  therefore keep their validation behavior locally owned and do not gain an
  import dependency on each other.

- **`BulkFileService` now validates its configured chunk size when the service
  is created and before every bulk write.** `BulkFileService.__init__()`
  validates `chunk_bytes` during construction. `upsert_large_bytes()` checks
  `self.chunk_bytes` again before storing anything, preventing callers from
  bypassing the constructor validation by changing the attribute afterward.

- **`attach_large_bytes()` and `attach_paths()` validate the chunk size before
  processing input.** `attach_large_bytes()` checks the value before creating
  sealed attachment records. `attach_paths()` validates before reading any
  path or building an archive, so an invalid chunk size is reported before a
  missing-file or archive-processing error.

- **`biometrics attach-paths` now enforces the same command-line chunk-size
  range as `vault encrypt-paths`.** The command accepts `--chunk-mb` values
  from 1 through 15 and rejects values outside that range before loading the
  keyring or asking for a passphrase. The default remains 8 MiB.

  The 15 MiB maximum applies only to the command-line interfaces. The direct
  Python APIs require a positive integer but do not impose an upper bound.

### Changed

- **`vault/store/bulk_file_service.py`.**
  - Added `_validate_chunk_bytes()`.
  - Added constructor validation in `BulkFileService.__init__()`.
  - Added write-time validation in `upsert_large_bytes()`.
  - Updated the standardized header's Edge cases and Known limitations to
    describe the validation behavior and its error.

- **`biometrics/engine/bulk_attachments.py`.**
  - Added `_validate_chunk_bytes()`.
  - Added validation to `attach_large_bytes()`.
  - Added validation to `attach_paths()` before paths are read or archived.
  - Updated the standardized header's Edge cases and Known limitations.

- **`biometrics/app.py`.**
  - Added `MAX_CHUNK_MB = 15`.
  - Updated `command_attach_paths()` to reject `--chunk-mb` values outside the
    supported command-line range.
  - Moved chunk-size validation ahead of keyring loading and passphrase
    collection.
  - Added help text for the option.
  - Matched the corresponding `vault encrypt-paths` error behavior.

- **`docs/KNOWN_ISSUES.md`.**
  - Moved KI-006 to Resolved.
  - Removed KI-006 from the open-issues table.

- **`docs/FILE_AND_BUNDLE_ENCRYPTION.md`.**
  - Updated "Chunk-size validation" to describe the corrected API and
    command-line behavior.
  - Clarified that the 15 MiB upper bound belongs to the commands rather than
    the direct APIs.

- **`version.py`.**
  - Updated `__version__` to `1.10.3`.

### Tests

- **`vault/tests/test_bulk_file_service.py`.** Three regression tests verify
  that:
  - zero and negative chunk sizes are rejected without storing records;
  - non-integer values and `True` are rejected;
  - changing `self.chunk_bytes` after construction is detected before a write,
    leaving the Vault without partial records.

- **`biometrics/tests/test_bulk_attachments.py`.** Four regression tests verify
  that:
  - invalid chunk sizes are rejected without storing attachment chunks;
  - non-integer values and `True` are rejected;
  - `attach_paths()` reports the invalid chunk size before reporting a missing
    path;
  - `biometrics attach-paths` rejects `--chunk-mb` values of `0`, `-1`, and
    `16` before the keyring function is called.

- The regression tests match the tests introduced in LTS-2028 1.3.13 and fail
  against that line's unfixed implementation.

- `python tests/run_tests.py --fast` ran 477 tests successfully, with 43 GUI
  tests skipped because the verification environment had no display.

- The two affected bulk test modules ran 28 tests successfully.

- The slow suite, which includes production-cost key derivation, was not run to
  completion for this release.

### Known issues

The code review that produced this correction identified two related cleanup
defects. Both remain open in this release and are recorded in
`docs/KNOWN_ISSUES.md`. They affect Official, LTS-2028 1.4.x, and LTS-2028
1.3.x.

- **KI-011: Deleting or replacing a Vault bulk bundle leaves its previous
  chunk records behind.** `VaultService.delete()` removes only the record it
  is given. Calling `upsert_large_bytes()` with an existing `record_id`
  replaces the manifest and overlapping chunks but does not remove chunks used
  only by the previous bundle.

  The defect was reproduced through the service API on all three supported
  lines. Replacing a bundle containing one manifest and three chunks with a
  one-chunk bundle left five records. Deleting the replacement manifest then
  left four chunk records behind.

  The desktop interface does not provide bundle deletion, so
  `python cli.py vault delete` is the only exposed deletion path. The CLI and
  desktop call paths were inspected but were not exercised end to end as part
  of this release.

- **KI-012: Replacing a Biometrics bulk attachment with a smaller attachment
  leaves stale chunks behind.** Reattaching content under an existing
  attachment name overwrites only the chunk names used by the new bundle.
  `remove_bulk_attachment()` subsequently removes only the chunks listed by
  the current manifest.

  The defect was reproduced through the attachment API on all three supported
  lines. After a four-chunk attachment was replaced by a one-chunk attachment
  and then removed, `doc.chunk1`, `doc.chunk2`, and `doc.chunk3` remained in
  the identity record.

- The Known limitations sections in
  `vault/store/bulk_file_service.py` and
  `biometrics/engine/bulk_attachments.py` now identify KI-011 and KI-012.
  These header updates do not change runtime behavior.

### Compatibility

- No cryptographic primitive, stored format, dependency, or valid-data behavior
  changes in this release.

- Bundles created by earlier releases with valid chunk sizes continue to open
  unchanged.

- A bundle previously created with a negative chunk size contains no data
  chunks. This release cannot reconstruct the missing content. Restoration
  continues to fail the existing reassembled-size check.

- `biometrics attach-paths --chunk-mb` now rejects values above 15. Earlier
  releases did not enforce that upper bound for this command. The new behavior
  matches `vault encrypt-paths`.

- The default command-line chunk size remains 8 MiB.

- Direct callers that supplied a non-`int` `chunk_bytes` value previously
  received a bare `TypeError` from `range()`. They now receive
  `BulkFileServiceError` or `BulkAttachmentError`, both of which inherit from
  `ValueError`.

- LTS-2028 1.3.13 and LTS-2028 1.4.3 carry the same correction. Their version
  strings differ from Official, and the 1.3.x documentation retains its
  line-specific description of the legacy envelope payload limit.

---

---

## [1.10.2] - 2026-11-22

A fix release for the move from `95_Identity_Tools` to
`98_Tooling/Identity_Tools`. After the move, Identity Tools could not find
BSR2 and reported `Encryption not found`; this release finds it again at
`97_Encryption/Official`, and the link now includes the signature module
BSR2 0.4.1-alpha added. LTS-2028 1.4.2 receives the same fix. LTS-2028 1.3.12
receives the documentation part only, because 1.3.x does not link to
`97_Encryption`.

### Fixed: the BSR2 link after the move into 98_Tooling

- **`crypto/encryption.py`: `ARCHIVE_ROOT` is four folders up, not three.**
  - **Before:** `Path(__file__).resolve().parents[3]`. With the tree at
    `95_Identity_Tools/<line>/` that was the archive folder. After the move to
    `98_Tooling/Identity_Tools/<line>/` it is `98_Tooling`, so the link looked
    for `98_Tooling/97_Encryption/Official`, found nothing, and every operation
    that needs encryption failed with `Encryption not found`.
  - **Now:** `parents[4]` (`crypto/` → line → `Identity_Tools/` →
    `98_Tooling/` → archive). `ENCRYPTION_DIR` is still
    `<archive>/97_Encryption/Official`; there is still no override and no
    absolute path. The status line still reads
    `Encryption: BSR2 Alpha 4 (0.4.1-alpha), from 97_Encryption/Official`.
  - The "not found" message now says to keep the `98_Tooling` and
    `97_Encryption` folders together in the same archive folder, instead of
    naming `95_Identity_Tools`.
- **`app.py`.** The `ENCRYPTION_WARNING` header note names `98_Tooling`
  instead of `95_Identity_Tools`.
- **`crypto/encryption.py`: the link includes `brisart_security_signature`.**
  BSR2 0.4.1-alpha added this module (Ed25519). The link is meant to cover
  every module `97_Encryption/Official` ships, and
  `test_every_library_module_in_97_encryption_is_linked` failed until it was
  added to `REQUIRED_MODULES` (now fourteen modules, available as
  `bsr2.signature`). Nothing in this line signs or verifies with it.

### Tests

- **`crypto/tests/test_encryption_link.py`.**
  - New `test_archive_root_is_the_folder_holding_98_tooling`: the application
    tree sits at `ARCHIVE_ROOT/98_Tooling/Identity_Tools/<line>` and
    `ARCHIVE_ROOT/97_Encryption` exists. This catches the next move that
    changes the folder depth.
  - The shared-parent check compares `ENCRYPTION_DIR.parent.parent` with the
    tree's third parent (the archive), not its second.
  - The missing-encryption subprocess test copies the tree to
    `<temp>/98_Tooling/Identity_Tools/<line>`, the real layout, so it tests
    a moved archive without `97_Encryption` rather than a different depth.
  - The not-found message assertion matches the new wording.
- Before the fix, with the tree at `98_Tooling/Identity_Tools/Official`:
  `python tests/run_tests.py --fast` failed with 4 failures and 163 errors,
  nearly all `Encryption not found`.
- After: `python tests/run_tests.py --fast` ran 470 tests, OK, 43 skipped
  (the GUI tests, which need a display; this environment has none).
  `crypto/tests/test_encryption_link.py` ran 15 tests, OK.
- The slow suite (production-cost key derivation) was not run to completion
  for this release.

### Documentation

- **`docs/README.md`.** The requirement reads "`98_Tooling` (which holds
  `Identity_Tools`) and `97_Encryption` sit together in the same archive
  folder."
- **`docs/BSR2_INTEGRATION.md`, "Integration boundary".** The layout diagram
  shows `98_Tooling/Identity_Tools/Official/crypto/encryption.py`; the module
  list and table include `signature` (linked, not used); a sentence says
  where the link looks and why.
- **`docs/SECURITY.md`.** The workflow names are now
  `test-98-identity-tools-*.yml`.
- **Python headers.** `crypto/encryption.py` (Settings, Edge cases, Known
  limitations, the module-by-module list) and
  `crypto/tests/test_encryption_link.py` (Edge cases, test count) describe the
  new layout.

### Outside this tree

Same pass, archive level: the `.gitignore` rules for keyrings, device keys,
passphrase files, and runtime `data/` pointed at `/95_Identity_Tools/` and
matched nothing after the move; they now point at
`/98_Tooling/Identity_Tools/`. The three CI workflows are renamed
`test-98-identity-tools-*.yml` and point at the new folders. See the archive
`CHANGELOG.md` entry of 2026-11-22.

### Compatibility

- No stored-format, keyring, or dependency change. Data written by 1.10.1
  opens unchanged.
- A line folder copied out of `98_Tooling/Identity_Tools`, or an archive with no `97_Encryption` beside `98_Tooling`, reports `Encryption not found`, as before.

---

## [1.10.1] - 2026-11-08

A documentation release; no code, stored-format, or dependency change. Four
things change. The threat model's closing list of protection limits becomes a
section that explains each limit and what you can do about it, and the rest of
the documentation points to it. The encryption migration record moves out of
`docs/BSR2_INTEGRATION.md` into its own document, `docs/ENCRYPTION_MIGRATION.md`.
KI-006 is corrected: it understated where the chunk-size fault can be reached.
The security policy's reporting and response sections, which were vague, are
rewritten with named channels, a severity scale, response targets, and a
disclosure policy. LTS-2028 1.4.1 and 1.3.11 receive the same pass.

### Documentation: what these tools do not protect against

- **`docs/BSR2_INTEGRATION.md`: "What these tools do not protect against"
  replaces "Protection limits".**
  - **Before:** the last section was a list of short phrases ("Master keys in
    process memory", "Keyrings co-located with protected data"), with no
    explanation and nothing a reader could act on.
  - **Now:** the section sits directly after "Primary caveat", so it is the
    second thing a reader sees. Each limit says in plain words what is
    exposed, and ends with *What you can do*. It is grouped by where the limit
    applies: the encryption itself, while the tools are running, files on
    disk, biometrics, packages and records, and hardware. The custody item
    also covers the integrity ledger (KI-004).
  - Facts were checked against the code, not copied from the old list:
    which fields stay readable without a passphrase (vault records, biometric
    identities and attachments, packages), where each keyring lives, the
    `unlock_attempts` field, and that the GUI keeps a store unlocked until
    Lock or the window closes. Only comparisons of secret values (keyring
    check values, factor bindings) are described as constant-time.
  - Restoring a bundle writes the rebuilt ZIP to a temporary directory
    before extracting it. The old list didn't say so; the new section does.
- **`docs/KNOWN_ISSUES.md`.**
  - The introduction says what is tracked here (defects, and limitations that
    still have a next step) and links to the new section for design limits,
    in place of the "Protection limits" link.
  - KI-005, KI-006, and KI-007 use the full template: numbered steps, an
    expected and an actual behavior that say what happens, and a next step
    with a workaround. "Tried/Ruled out" is spelled "Tried / Ruled out"
    everywhere, as in the template.
  - **KI-006 is wider than it said.** It described direct API callers only.
    `biometrics attach-paths --chunk-mb` also passes its value through
    unchecked, so `--chunk-mb 0` reaches the same fault; only
    `vault encrypt-paths` checks the range (1 to 15). The title is now
    "Biometrics bulk CLI and direct bulk APIs do not validate chunk size", and
    the environment, steps, and workaround include the CLI. The code is
    unchanged; the fix is still a separate code change.
- **`docs/FILE_AND_BUNDLE_ENCRYPTION.md`.** "Direct API chunk-size limitation"
  becomes "Chunk-size validation" and states which commands check the size and
  which don't (KI-006). It no longer mentions an envelope payload limit,
  which sealing has not had since 1.10.0.
- **`docs/README.md`.** The opening caveat links to the new section, and
  "Important boundaries" says that it is a short list and links to the full
  one.
- **`docs/SECURITY.md`.** "Assurance boundaries" links to the new section for
  each item, and marks physical-device validation as Official only. The text
  stays identical in all three lines.
- **Component READMEs.** `vault/`, `biometrics/`, `packages/`, and `crypto/`
  link their security sections to the new section. `biometrics/README.md`
  adds that each attachment's filename, size, and SHA-256 are readable without
  unlocking.
- **Python headers.** `vault/store/bulk_file_service.py` and
  `biometrics/engine/bulk_attachments.py` no longer tell callers to stay
  "below the envelope payload limit", which no longer exists.
  `biometrics/app.py` notes that `--chunk-mb` is not range-checked (KI-006).
- **`docs/BSR2_INTEGRATION.md`, "Custody chains and audit files".** The
  ledger paragraph names the Official-only integrity ledger, links to it, and
  cites KI-004, in place of "where the current application supplies an
  integrity ledger".

### Documentation: encryption migration gets its own document

- **`docs/ENCRYPTION_MIGRATION.md` (new).**
  - **Before:** the migration record was one long section of
    `docs/BSR2_INTEGRATION.md`, between the integration boundary and master
    keys, and five other documents linked into the middle of it. How to
    actually migrate was spread across the Vault, Biometrics, and Packages
    READMEs.
  - **Now:** the record has its own file, unchanged in substance, with its
    headings promoted one level. It opens with "Before you migrate" (keep a
    copy, nothing changes until you agree, the passphrase stays and the
    recovery code is replaced) and "Migrating each store", one table with the
    CLI command and GUI prompt for Vault, Biometrics, and Packages.
- **`docs/BSR2_INTEGRATION.md`.** "Encryption migration" is now a short
  pointer to the new document, so the existing anchor still resolves. The
  file goes back to one subject: how BSR2 is linked and what it protects.
  "Related documentation" lists the new document.
- **Links.** `docs/README.md`, `crypto/README.md`, `vault/README.md`,
  `biometrics/README.md`, and `packages/README.md` link to
  `docs/ENCRYPTION_MIGRATION.md` instead of
  `BSR2_INTEGRATION.md#encryption-migration`. `docs/README.md`'s
  Documentation list gives the migration document its own entry.

### Documentation: security reporting and response policy

- **`docs/SECURITY.md`, "Reporting".**
  - **Before:** reports were to use "a private reporting channel": GitHub
    Private Vulnerability Reporting where enabled, otherwise "a private contact
    channel published by the maintainer". Neither was named. GitHub releases
    have been discontinued, but the repository's private advisory route still
    applies, so it stays. Nothing said what counts as a security issue.
  - **Now:** two named private channels, handled the same way. GitHub
    Private Vulnerability Reporting is preferred. Email to
    Jason@brisartresearcharchive.com, with a fixed subject format, takes the
    full report for anyone who would rather not use GitHub. Public reports
    before disclosure are ruled out. New subsections define what is a security issue, list what is handled
    as an ordinary known issue instead (documented design limits, open KIs,
    1.3.x's KI-008 to KI-010, ended releases, an attacker already controlling
    an unlocked session), and limit testing to data the reporter owns.
  - The report fields now follow the `docs/KNOWN_ISSUES.md` template, plus
    **Impact** and **Disclosure**, and ask for `python cli.py version` and
    `python tools/envinfo.py` output from the affected line's folder. Reports
    containing real secrets are deleted once a reproduction is rebuilt.
- **`docs/SECURITY.md`, "Severity" (new).** Critical, High, Medium, and Low
  are defined against the protections the tools claim, not the limits they
  already document. The maintainer's assessment is final and explained when it
  differs from the reporter's.
- **`docs/SECURITY.md`, "Response expectations".**
  - **Before:** acknowledgement "within a few days", an assessment "within
    roughly two weeks", and no fix targets.
  - **Now:** a table: acknowledgement within 3 days, triage within 14 days,
    status updates at least every 14 days, and fix targets by severity
    (Critical 14 days, High 30, Medium 90, Low next scheduled release). They
    remain targets for a solo maintainer, not service levels, but a missed
    target is announced in advance with a new date. "Fix shipped" means on
    every affected supported line. Every report closes with a stated outcome:
    fixed, won't fix, not reproduced, duplicate, or not a security issue.
- **`docs/SECURITY.md`, "Disclosure" (new).** Coordinated disclosure: no
  publication until the fix ships on every affected line, or 90 days after
  triage, whichever comes first, unless agreed otherwise. Fixes are recorded
  as changelog **Security** entries with an identifier, severity, affected
  versions, files, and the gap closed; won't-fix issues go to
  `docs/KNOWN_ISSUES.md`. Credit is opt-in.
- The text is identical in all three lines.

### Compatibility

No code, stored-format, or dependency change. Python edits are limited to
module docstrings and the version string: `version.py` moves from 1.10.0 to
1.10.1, which `python cli.py version` and Help > About report. Data written by
1.10.0 and 1.10.1 is identical. Every Markdown link and heading anchor in the
line resolves, checked by resolving each link's file and heading after the
split.

---

## [1.10.0] - 2026-11-08

Identity Tools Official adopts BSR2 as its only encryption and
migrates existing data to it. This is Identity Tools' part of the archive-wide
cryptography migration recorded in the root `CHANGELOG.md` (2026-10-23).
LTS-2028 1.4.x adopts exactly the same changes in 1.4.0: it shares Official's
architecture, and all encryption in both comes from `97_Encryption`. Official
differs only by its non-security extras. LTS-2028 1.3.x keeps vendored BSR2 and
does not adopt them.

The release does three things. First, the four BSR2 files vendored into
`vendor/` are gone: every module that needs encryption reaches
`97_Encryption/Official` through one link, `crypto/encryption.py`, which links
all thirteen BSR2 modules. Second, new data is written in BSR2's current formats: sealed format v3 (`BSR2-S64-SIV`), BSR-STREAM-1
above 16 MiB, BSR2-MHF-1 keyring wrappers, BSR2-S64 factor bindings, and BSR2-S64
typed-text package keys. Third, data in the previous encryption keeps opening,
and every tool offers to migrate it. The GUI asks with a pop-up before
unlocking, the CLIs print a notice and provide `migrate` commands, and OK
re-encrypts the store in place. The previous encryption is kept only as a
reader and is removed entirely in a later release.

The per-project migration record the archive policy asks for is in
`docs/BSR2_INTEGRATION.md`, under "Encryption migration": previous and
replacement implementation, affected formats, migration method, in-place
behaviour, remaining compatibility, rollback limits, and tests.

### Added

- **`crypto/encryption.py`: the single link to BSR2.** It
  locates `<archive root>/97_Encryption/Official` and imports all thirteen
  library modules: `primitives`, `sponge`, `entropy`, `drbg`, `envelope`, `aead`,
  `stream`, `kdf`, `keys`, `recovery`, `archive`, `cli`, and `version`.
  `require()` hands them out as a namespace of modules (`bsr2.aead.seal`,
  `bsr2.kdf.derive_key`), so every call site names the construction it uses.
  The link is refused, and reported as `Encryption not found: <reason>`, in
  five cases:
  - the directory or a module is missing;
  - a module fails to import;
  - a `brisart_security_*` module was already loaded from somewhere else;
  - the library lacks a format Identity Tools writes or reads (legacy
    envelope v2, sealed format v3, stream format 1, BSR2-MHF-1).

  It also holds `MIGRATION_NOTICE`, the one message every CLI and GUI shows
  before migrating.

- **`biometrics/identity/encryption_migration.py` (new).** It migrates a
  biometrics data directory. The keyring goes first, through the throttled
  path. Then each identity file is rewritten on its own, and only if something
  changed. Templates and attachments are resealed under their own contexts.
  This machine's legacy device binding is re-bound when it verifies here. An
  interrupted run leaves everything readable and can be run again. Device
  bindings recorded on another machine are reported. They don't count towards
  `needs_migration()`, so the prompt doesn't return on every unlock.

- **`crypto/tests/legacy_fixtures.py` (new, test support).** A real v1
  keyring, plus writers for legacy envelopes and bindings, so migration tests
  can build pre-1.10.0 data without the pre-1.10.0 code. It is not collected
  as a test module.

- **Migration tests:** `vault/tests/test_vault_migration.py`,
  `biometrics/tests/test_encryption_migration.py`, and
  `packages/tests/test_package_migration.py` (see Compatibility).

- **`packages/tests/test_demo.py` (new).** `packages/demo.py` had no test of
  its own. The new test runs the demo cycle in memory, then runs it with
  `save_to_disk=True` and opens the saved package as Bob from his saved
  passphrase.

### Changed

- **`crypto/envelope.py`: current formats, no size cap, legacy read and
  reseal.** `seal_bytes()` writes `{"format": "BSR2-S64-SIV/3", "data":
  <base64>}` up to 16 MiB and `{"format": "BSR-STREAM-1", ...}` above it, so
  the old 16 MiB ceiling is gone. Length hiding uses BSR2's
  `block` padding, the same 256-byte buckets this module used to add by hand.
  `open_bytes()` dispatches on shape and still opens legacy v2 envelopes.
  Failures in any format surface as `EnvelopeAuthenticationError`. Two new
  functions:
  - `is_legacy()` reports whether a payload is a legacy v2 envelope.
  - `reseal()` re-encrypts a legacy payload in the current format under the
    same key and context. Every store's migration uses it.

  On the verification machine a 20 KB round trip took 1.4 s in v3, against
  11.2 s with the legacy envelope.

- **`crypto/keyring.py`: format v2, BSR2-MHF-1, and `migrate()`.**
  - **Per-wrapper KDF:** each wrapper records its own KDF: BSR2-MHF-1 with
    encoded parameters (8,192 blocks, 1 MiB, one pass by default) or the
    legacy iterated KDF.
  - **v1 keyrings:** a v1 keyring is read through a v2 view and left exactly
    as stored until a wrapper is replaced, so unlocking it keeps it readable by
    the release that wrote it. Keys the keyring does not own, such as the
    biometrics attempt state, are kept through that conversion.
  - **`needs_migration` and `migrate(passphrase)`:** `migrate()` unlocks first,
    so a wrong passphrase changes nothing. It then re-derives the passphrase
    wrapper with BSR2-MHF-1 and replaces a legacy recovery wrapper with a newly
    issued recovery code, returned once. The old code can't be re-derived
    because it is never stored.
  - **Limits and check value:** stored MHF parameters are capped at 65,536
    blocks and four passes. New and rewritten check values are BSR2-S64 MACs.
  - **Randomness:** master keys and recovery codes come from BSR2's entropy module, five bits per recovery-code character.
  - **`create()` signature:** it takes `memory_blocks` (default
    `MEMORY_BLOCKS`, read at call time) in place of `iterations`.
  - **Unlock time:** a new keyring unlocks in seconds instead of the minute or
    more the 10,000-iteration floor took.

- **`crypto/factors.py`: BSR2-S64 bindings.** `bind_factor()` writes
  `bsr2$mac64$...`. `verify_bound_factor()` also accepts the legacy
  `bsr2$keyed_mac$...` form, and `is_legacy_binding()` recognises it.

- **`crypto/rng.py`: BSR2 DRBG seeded from its entropy module.**
  Seeds come from `entropy.system_entropy`, which health-checks operating-system
  output, instead of `secrets`. The DRBG is reseeded before its own lifecycle
  limits, so long runs don't hit them.

- **`vault/store/vault_service.py`: `needs_encryption_migration(path)` and
  `VaultService.migrate_encryption(passphrase)`.** Migration runs under the
  same attempt limiting as `unlock()`. It reseals every legacy record (JSON,
  file, bundle manifest, bundle chunk) and writes the vault file once,
  atomically. A record that fails to authenticate under its stored context
  (KI-005) is left alone and reported. `vault/reports/audit_log.py` accepts the
  new `encryption_migrated` action.

- **`biometrics/identity/keyring_access.py`: `migrate_with_passphrase()`.** It
  wraps `Keyring.migrate()` in the same attempt gate as unlocking, and writes
  the migrated keyring with its attempt state.

- **`packages/ciphers.py`: content keys and typed-text keys from BSR2.** `new_content_key()` uses its entropy module.
  `text_master_key()` is now the single typed-text derivation (a BSR2-S64 hash)
  for the CLI, GUI, and demo. Before, three separate copies of an unsalted
  SHA-256 lived in `packages/main.py`, `packages/demo.py`, and
  `gui/tabs/tab_packages.py`. `legacy_text_master_key()` keeps SHA-256 only
  for opening and migrating packages keyed before 1.10.0.

- **`packages/package.py`: per-recipient migration.**
  `recipient_key_from_text()` picks the current text key, or the legacy one
  for a recipient not yet migrated. `needs_encryption_migration()` and
  `migrate_recipient()` reseal the payload and re-seal that recipient's key
  slot and verifier under the current key. They also append a
  `payload_rewrapped` custody entry with `"reason": "encryption_migration"`.
  The content key does not change, so recipients not yet migrated keep opening
  the package. `packages/audit.py` accepts `encryption_migrated`.

- **CLIs: migration commands and notices.**
  - **New commands:** `vault migrate`, `biometrics migrate`, and
    `package migrate --identity-id ID`. Each shows `MIGRATION_NOTICE`, asks
    `Migrate now? [y/N]` (`--yes` skips the question), and reports what was
    migrated, what was left, and any new recovery code.
  - **Unlock notice:** an unlock or open that touches legacy data prints a
    one-line notice pointing to the matching command.
  - **`cli.py`:**
    - `version` prints the encryption link.
    - A new `encryption` tool runs BSR2's own toolkit unchanged:
      keys, file encryption, sealed messages, hashing, archives with recovery
      records, `kdf-bench`, and `selftest`.
  - **Exit status 3:** `vault/app.py`, `biometrics/app.py`, `packages/main.py`,
    and `cli.py encryption` exit 3 with `Encryption not found: ...` when the
    link is unavailable.

- **GUI: the migration pop-up.**
  - **Vault and Biometrics tabs:** unlocking a store that holds legacy data
    first shows `MIGRATION_NOTICE`, plus a note that a new recovery code may be
    issued.
    - OK migrates in place of the unlock, then shows what was re-encrypted,
      what was left, and any new recovery code.
    - Cancel unlocks with the previous encryption and asks again next time.
  - **Packages tab:** opening a package asks the same question for that
    recipient.
  - **Shared text:** `gui/widgets/dialogs.py` holds `KEYRING_MIGRATION_NOTE`
    and `migration_summary()`, used by both tabs.
  - **Encryption link:** `app.py` shows the link in a status line and in
    Help > About, as `..., from 97_Encryption/Official`. When encryption is
    not linked, a warning pop-up at start-up gives the reason and says to
    proceed with caution. The pop-up is Official-only; LTS-2028 keeps the
    status line and error dialogs.

- **`crypto/errors.py`: `EncryptionNotFoundError(RuntimeError)`.** It sits
  outside the `Bsr2IntegrationError` family. That way a missing link is never
  reported as a wrong passphrase or a non-matching factor.

- **`tests/run_tests.py`: the root is found without `vendor/`, and the slow
  list matches the new costs.** Keyring round trips now run in the fast suite.
  Slow are `LegacyKeyringTests` and `LegacyKeyringVaultMigrationTests`, which
  unlock a real v1 keyring through the legacy KDF.

- **Documentation.**
  - `docs/BSR2_INTEGRATION.md`:
    - New "Encryption migration" section.
    - A table of each BSR2 module's job.
    - The hashing that stays outside the link, none of it encryption: the
      legacy text key, the SHA-256 integrity fingerprints in
      `common/hashing.py`, and the ONVIF-mandated SHA-1 digest.
  - `crypto/README.md`: a table of formats written and still read.
  - `docs/SECURITY.md`: the revised release-line policy, identical in both
    lines. LTS-2028 is the baseline for security changes, the lines share one
    architecture, and all encryption comes from `97_Encryption`. It also
    lists the features that stay Official-only, since LTS-2028 takes no new
    features until it reaches end of life.
  - Migration sections in `vault/README.md`, `biometrics/README.md`,
    `packages/README.md`, and `docs/README.md`.
  - `docs/FILE_AND_BUNDLE_ENCRYPTION.md`, `docs/KNOWN_ISSUES.md` KI-003, and
    the headers of the bulk-file modules and GUI tabs: they no longer give a
    16 MiB envelope cap as the reason for chunking. Chunking is unchanged and
    remains the stored bundle format.

### Removed

- **`vendor/`** (four byte copies of BSR2 0.3.0-alpha and `README.md`),
  **`crypto/vendor.py`** (its `sys.path` shim), and
  **`tests/test_bsr2_vendor_integrity.py`** (digest pins for those copies).
- **`crypto/factors.py`: `hash_factor()`, `verify_factor()`,
  `is_factor_hash()`, `needs_rehash()`, `is_legacy_digest()`,
  `is_bound_factor()`.** Nothing outside `crypto/` called them, and Identity
  Tools stores no password-derived factor hashes.
- **`crypto/envelope.py`: `MAX_PAYLOAD_BYTES` and `PADDING_BLOCK_BYTES`.**
  There is no cap to report, and padding is BSR2's now.
- **`gui/tests/test_tab_packages.py`: the four `_derive_master_key` tests.**
  The method is gone. The derivation is tested where it now lives, in
  `packages/tests/test_package_migration.py`.

### Fixed

- **The Official CI workflow targets the real tree.** Renamed from
  `test-95-identity-tools-main.yml` to
  `.github/workflows/test-95-identity-tools-official.yml`. It named
  `95_Identity_Tools/main`, which does not exist. It now names `Official`,
  changes under `97_Encryption/Official/**` also trigger it, and its
  self-trigger path, display name, and report names say `official` instead of
  `main`.
- **CI for both LTS-2028 lines.** `test-95-identity-tools-lts2028.yml` named
  `95_Identity_Tools/LTS-2028`, which no longer exists. It is replaced by
  `test-95-identity-tools-lts2028-1.3.yml` and
  `test-95-identity-tools-lts2028-1.4.yml`, one per LTS-2028 line.
- **`docs/SECURITY.md` describes the three supported lines**, their end of
  life, how security fixes reach each one, 1.3.x's known vulnerabilities, and
  the three-month minimum for migration in 1.4.x, in place of the two-line
  policy. All three lines carry the identical text.
- **`docs/README.md` names the application roots `Official/`,
  `LTS-2028 1.4.x/`, and `LTS-2028 1.3.x/`** instead of `main/` and
  `LTS-2028/`. It and `docs/BSR2_INTEGRATION.md` now say migrated data can't
  be read by any LTS-2028 1.3.x release, not only by 1.3.10.
- **How migration decrypts and re-encrypts, step by step.** The "Encryption
  migration" record in `docs/BSR2_INTEGRATION.md` explains how old data is
  recognized, how it is read without being changed, the three steps of
  `crypto.envelope.reseal()`, the four steps of `Keyring.migrate()`, how
  device bindings and package verifiers are replaced, and when each store
  writes its files. The vault, biometrics, and packages READMEs link to it.
- **Migration pop-up text.** `crypto.encryption.MIGRATION_NOTICE` names the
  previous encryption as BSR2 Alpha 3, and says migrated data can't be opened
  by any LTS-2028 1.3.x release, or by Official 1.9.2 and earlier. The same
  wording replaces "1.3.10, or earlier" in the module headers and READMEs that
  said it.
- **Documentation audit.** Every file's documentation was checked against the
  code: each Python header's `File:` path, its six sections in order, its
  "Depends on" and "Imported by" lists against the real imports, 252 documented
  constants, and 1,193 documented error messages. All of them now match.
  Corrected along the way: the "Imported by" lists of the `crypto/` modules and
  `biometrics/identity/` modules that the migration code imports; `cli.py`'s
  "Depends on" list (`crypto.errors`); the test count in
  `vault/tests/test_vault_migration.py`; "Residual Risks" references, which now
  name "Protection limits"; the remaining `main` references in
  `docs/KNOWN_ISSUES.md`, `docs/INTEGRITY_LEDGER.md`, `version.py`, and
  `biometrics/app.py`; the package typed-text key, which
  `docs/BSR2_INTEGRATION.md` and `gui/README.md` described as SHA-256; and
  headers that told project history instead of current behavior (`liveness.py`,
  `enrollment.py`, `verification.py`, `hashing.py`, `timestamps.py`, and the
  collapsed bullet lists in `common/integrity_ledger.py`). Overlong Markdown
  lines are re-wrapped without changing their wording.
- **Readability pass.**
  - `docs/README.md` gains a "Quick start": a first vault in five
    commands, run end to end before writing it down, and what each step asks
    for.
  - `docs/README.md` opens with a note naming the line it documents, its
    Layout lists what each folder is for, and its Documentation section is now
    links grouped as Start here, Each tool, Shared code, and History.
  - `docs/KNOWN_ISSUES.md` opens with an "Open issues at a glance" table
    linking each entry, and says how to report a new problem. Its template's
    **Environment** field points to `python tools/envinfo.py`.
  - `docs/BSR2_INTEGRATION.md` opens with a list of contents. Its
    "Encryption migration" record uses subheadings for each policy item and each
    step.
  - `docs/SECURITY.md` says which commands print the version and environment
    for a report, and states response targets directly. The text is identical in
    all three lines.
  - Plain-text references to other documents are now links, and every link and
    heading anchor in the documentation resolves. All 160-plus commands shown in
    the documentation were checked against each tool's `--help`: every
    subcommand and option exists.
  - `docs/KNOWN_ISSUES.md`: KI-005 to KI-007 give their reported date,
    2026-11-08, matching the LTS-2028 lines.
  - Headers no longer describe a single-envelope size limit that sealing no
    longer has (`gui/tabs/tab_biometrics.py`, `vault/README.md`,
    `vault/store/bulk_file_service.py`).
  - Leftovers from earlier edits are gone: "BSR2 comes from BSR2", "(new)" in
    two GUI docstrings, and stray spaces inside file paths in
    `crypto/attempt_store.py`.

### Release lines

Brisart Identity Tools now holds LTS-2028 as two separate lines. Together
with Official, it maintains three lines, and all of them receive security
updates until their designated end of life (31 December 2028 for both
LTS-2028 lines). The policy is in `docs/SECURITY.md`, identical in all three
lines.

- **LTS-2028 1.3.x:** the original LTS-2028 line, kept on vendored BSR2
  0.3.0-alpha and its original contract. Its encryption has known
  vulnerabilities that it will not fix, because fixing them means changing
  the encryption:
  - the keyring passphrase KDF is not memory-hard (KI-008, Medium);
  - the v2 envelope is not nonce-misuse resistant (KI-009, Low);
  - the vendored randomness lacks BSR2 Alpha 4's fork, copy, and
    constant-sample protections (KI-010, Low).

  They are recorded in 1.3.x's own `docs/KNOWN_ISSUES.md`. This release is
  not affected: Official uses BSR2's current formats and
  randomness for everything it writes. It uses the previous encryption only to
  read existing data, and offers to migrate that data.
- **LTS-2028 1.4.x:** the original LTS-2028 line, with the new encryption as
  its only change, starting with 1.4.0. It ships the same encryption and
  migration as this release, and keeps the migration until at least
  8 February 2027.

### Compatibility

- **BSR2 is required.** The `95_Identity_Tools` and
  `97_Encryption` folders must sit together in the same folder, with BSR2 Alpha 4 (0.4.0-alpha) or later in `97_Encryption/Official`. Where that
  folder is doesn't matter. Kept apart, the tools start, report
  `Encryption not found` with that instruction, and the GUI warns with a
  pop-up at start-up. Nothing falls back to other cryptography, and no message
  shows the absolute location of the archive.
- **Backward compatible for reading.** Everything Official 1.9.2, LTS-2028
  1.3.10, and earlier write
  still opens, unlocks, and verifies: legacy envelopes, v1 keyrings, legacy
  bindings, and SHA-256 text-keyed packages. It stays that way until a later
  release removes the previous encryption. Nothing is rewritten on read:
  unlocking, reading, or answering Cancel to the pop-up leaves a store readable
  by the release that wrote it. A v1 keyring is kept exactly as stored until a
  wrapper is replaced, and only attempt-limiting state is written. Data changes
  format only when it is migrated or written again.
- **Migration is in place and one-way.** Each store is rewritten through
  atomic replacement, with no copy of the previous files kept. Migrated or
  newly written data cannot be read by Official 1.9.2, LTS-2028 1.3.10, or
  earlier. LTS-2028 1.4.0 uses the same formats and reads it.
- **Recovery codes.** A recovery code that used the previous KDF is replaced
  during migration by a new one, shown once. The old code doesn't open the
  migrated keyring, but still opens any earlier copy of it. Passphrases are
  unchanged.
- **What can stay legacy after migrating:**
  - a vault record that fails to authenticate under its stored context
    (KI-005);
  - a device binding recorded on another machine;
  - package recipients who have not migrated yet.

  Each is reported. Running the migration again finishes whatever can be
  finished.
- **API changes, all inside `crypto/` and `packages/`:**
  - `encryption.require()` returns modules.
  - `Keyring.create(iterations=...)` is now `Keyring.create(memory_blocks=...)`.
  - `KEYRING_FORMAT` is v2.
  - The removals listed above.

  The three tests that asserted the legacy envelope's field names now assert
  the v3 shape.
- **Test results.** The full suite passes against linked BSR2 Alpha 4
  (0.4.0-alpha). The 43 skips are GUI tests that need Tk, which the verification
  environment lacks.
  - `--fast`: 469 tests passed, 43 skipped.
  - `--slow`: 47 tests passed across all nine slow classes, including both
    real-v1-keyring vault tests and `LegacyKeyringTests`.
- **What the tests cover:**
  - `crypto/tests/test_encryption_link.py`: payloads and a binding sealed by
    1.9.2 itself open, reseal to v3 with identical content, and re-bind.
  - `crypto/tests/test_keyring.py`: loading a v1 keyring leaves it as
    stored. A real v1 keyring unlocks without being rewritten, then migrates;
    its new recovery code unlocks and the old one no longer does.
  - Vault, biometrics, and package tests, each covering:
    - legacy data reads before migration;
    - migration is complete, with content unchanged;
    - a wrong passphrase or text changes nothing;
    - partial migration is reported;
    - a second run migrates nothing.
  - `vault/tests/test_vault_migration.py` (slow): a vault on the real v1
    keyring is unlocked and read without changing anything an older release
    reads, then migrates end to end.
- **Checked by hand on the verification machine, against data written by
  LTS-2028's own code (vendored BSR2 Alpha 3, 0.3.0-alpha):** a vault with two JSON
  records and a file record, a biometrics keyring and identity with a
  fingerprint template, an attachment, and a device binding, and a package
  with two recipients.
  - **Before migrating:** the 1.10.0 CLIs read all of it, and each printed
    the migration notice. `vault get` returned the records, and
    `vault decrypt-file` and `biometrics extract-attachment` returned
    byte-identical files. `biometrics verify` matched, and `package open`
    worked for both recipients.
  - **Reading without migrating:** the vault and biometrics files were
    unchanged apart from attempt state, and LTS-2028 still opened them
    afterwards.
  - **Migrating:** `vault migrate`, `biometrics migrate`, and
    `package migrate` (one recipient at a time) re-encrypted everything.
    Keyrings became v2 with BSR2-MHF-1 wrappers, every payload became
    `BSR2-S64-SIV/3`, and bindings became `mac64`. Contents stayed
    byte-identical. The new recovery codes unlocked and the old ones were
    rejected. A recipient not yet migrated still opened the package. Running
    the migration again migrated nothing. LTS-2028 1.3.10 could not open the
    migrated vault, biometrics data, or package, as stated above.
  - **The pop-up:** Tk is not available in the verification environment, so
    the Vault, Biometrics, and Packages tabs were driven with Tk stubbed out.
    Everything else was real code on the LTS-written data. Cancel unlocked or
    opened with the previous encryption, left the data as written, and the
    question came back next time. OK migrated, showed the summary with the
    new recovery code, and the question did not come back.

---

## [1.9.2] - 2026-10-12

A documentation-overhaul and correctness release bringing the current codebase,
module headers, READMEs, architecture documentation, and regression coverage back
into alignment with the behavior actually implemented by BrisartIdentityTools.

The documentation review also exposed several correctness issues in the CLI, GUI,
package persistence, biometric video commands, and test classification. Those
issues are corrected in this release. Main-only functionality, including
`hardware/`, the Integrity Ledger, and the saved-files package demo, remains in
place and is unaffected except where shared infrastructure is explicitly listed
below.

No stored Vault, identity, keyring, biometric-template, attachment, package,
custody-chain, hardware, or Integrity Ledger format changed. There is no data
migration.

### Security

- **`gui/tabs/tab_biometrics.py`: GUI-created Biometrics keyrings now use the
  same protected write path as the command-line interface.** The Biometrics tab
  previously created `keyring.json` using a normal `open()` / `json.dump()`
  write, while the CLI already used the shared atomic-write infrastructure and
  requested owner-only (`0600`) permissions on POSIX. New GUI-created keyrings
  are now written through `common.atomic_io.atomic_write_json()` with
  `SENSITIVE_FILE_MODE`, and loading an existing keyring calls
  `warn_if_permissive()`. This removes the protection mismatch between the GUI
  and CLI paths. POSIX permission enforcement remains platform-specific and is
  not claimed on Windows.

### Fixed

- **`cli.py`: tool exit statuses are now propagated correctly.** The
  `biometrics`, `vault`, and `package` dispatcher handlers previously discarded
  the status returned by the underlying tool and returned `0` themselves. This
  meant commands such as a biometric verification could report `NO MATCH` or an
  error while the top-level `python cli.py ...` process still exited
  successfully. Each handler now returns the underlying tool's exit status:
  `0` for success, `1` for a negative result, and `2` for a reported error.
  Scripts that call `python cli.py` and check its exit status will now see `1`
  or `2` where they previously always saw `0`.

- **`cli.py`: the `gui` command now imports the actual GUI entry point.** The
  dispatcher attempted to import `gui.app`, even though the GUI shell was moved
  to the repository-root `app.py` during the 1.2.0 architecture split. Running
  `python cli.py gui` therefore raised `ImportError`. The dispatcher now imports
  the root-level `app.py` and calls the same `main()` entry point used by
  `python app.py`. No GUI files were moved as part of this fix.

- **`packages/main.py` and `gui/tabs/tab_packages.py`: package saves are now
  atomic.** Package writes previously used direct file writes, allowing an
  interrupted write to leave the destination file partially written or
  truncated. Both the CLI and GUI package-save paths now use
  `common.atomic_io.atomic_write_json()`, so the completed replacement is
  performed through the project's shared atomic-write mechanism. Package file
  permissions are otherwise unchanged. The helper does not provide file
  locking, so concurrent writers targeting the same package can still overwrite
  one another's updates. Main's saved-files demonstration workflow remains
  otherwise unchanged.

- **`biometrics/app.py`: `record-video` and `probe-video` now report ordinary
  input failures without uncaught tracebacks.** `record-video` now creates a
  missing parent directory before writing its BRVID output. A request with
  `--frames 0` is rejected with an `error:` message and exit status `2`.
  `probe-video` likewise reports a missing file or invalid/non-BRVID input as an
  `error:` and exits `2` instead of allowing the underlying exception to escape
  to the command line.

- **`tests/run_tests.py` and the bulk-attachment regression tests: `--fast`
  no longer includes work that belongs to the slow test set.** The
  bulk-attachment tests now use 256-byte chunks rather than 32 KiB chunks,
  retaining their chunking coverage without doing unnecessarily large amounts
  of encrypted test work. `vault.tests.test_sealed_vault.VaultFilePermissionTests`
  is now registered in `SLOW_TEST_CLASSES` because it exercises the real
  password KDF. This changes test classification and test fixture size only;
  production encryption behavior is unchanged.

- **`biometrics/config/settings.py` and `biometrics/README.md`: biometric
  settings documentation now distinguishes compatibility values from active
  runtime configuration.** The previous header implied that
  `TEMPLATE_WIDTH`, `TEMPLATE_HEIGHT`, `GRID_SIZE`, and `DEFAULT_THRESHOLD`
  directly controlled the current extraction and matching paths even though
  those paths do not read these values. The documentation now identifies them
  accurately and points to the code where extraction geometry and matching
  thresholds are actually defined. The existing names and values are
  unchanged.

- **`version.py`: the module header now describes the version constant it
  actually contains.** The standardized header previously stated that the
  module defined no constants even though it defines `__version__`. The header
  now reflects the module's real responsibility, and the Current-line version
  is `1.9.2`.

### Added

- **`tests/test_cli_dispatcher.py`:** added regression coverage confirming that
  the top-level dispatcher preserves the exit statuses returned by Biometrics,
  Vault, and Packages. Coverage also verifies that the `gui` command reaches
  the root GUI shell's `main()` function without needing to open the actual
  application window; that GUI-dispatch test is skipped when Tkinter is
  unavailable.

- **`gui/tests/test_tab_biometrics.py`:** added coverage for the GUI Biometrics
  keyring-creation path, including verification that the serialized keyring
  state is written and, on POSIX, that a newly created keyring receives mode
  `0600`. The permission-specific test is skipped on Windows.

- **`biometrics/tests/test_video_support.py`:** expanded regression coverage for
  the `record-video` and `probe-video` command error paths, including zero-frame
  recording requests and missing or invalid probe inputs.

### Changed

- **Repository-wide documentation was rewritten against the current
  implementation.** `docs/README.md` and the READMEs under `vault/`,
  `biometrics/`, `packages/`, `gui/`, `common/`, and `crypto/` now describe
  the behavior and limitations of the code they accompany rather than carrying
  forward stale descriptions from earlier layouts.

- **`docs/BSR2_INTEGRATION.md`:** rewritten around the actual integration
  boundary and threat model so the document distinguishes the guarantees
  supplied by the surrounding application from the guarantees and limitations
  of the vendored BSR2 implementation.

- **`docs/SECURITY.md`:** revised so project maintenance/support policy and
  security assurance are described separately rather than implying that long
  support lifetime itself provides additional security assurance.

- **`docs/KNOWN_ISSUES.md`:** KI-003 now documents the memory and temporary-
  storage considerations of bulk encryption alongside its throughput
  limitation.

- **Biometric documentation was corrected to match the implemented feature
  shapes and checks.** Fingerprint extraction is documented as operating on
  128x128 input with an 8x8 grid and producing a 192-value feature vector.
  Video extraction is documented as producing a 72-value vector composed of
  36 spatial and 36 motion values. `record-video` is described as generating
  synthetic BRVID data, and the video liveness mechanism is described as a
  motion-presence check rather than general anti-spoofing.

- **Bulk-encryption documentation now distinguishes envelope-size handling from
  resource usage.** Chunking allows content larger than the per-envelope limit
  to be processed, but is no longer described as eliminating memory,
  temporary-storage, or throughput constraints.

- **Package key and history documentation was tightened.** Package
  text-to-key prompts are documented as using a single unsalted SHA-256
  derivation for demonstration use. Custody chains and audit files are
  documented as unkeyed history/tamper-evidence mechanisms rather than
  authenticated or immutable records.

- **`docs/FULL_FILE_ENCRYPTION.md` was renamed to
  `docs/FILE_AND_BUNDLE_ENCRYPTION.md`.** The new filename reflects that the
  document covers both individual-file encryption and the bundled
  file/folder/drive workflows. References to the old documentation filename
  were updated.

- **Python module headers were standardized.** Project-owned Python modules now
  use the six-section documentation structure: Purpose,
  Communication / relationships, Settings / parameters, Edge cases,
  Known limitations, and Examples. The pass also corrected headers whose
  descriptions had drifted from the implementations beneath them.

### Verification

- Regression coverage was expanded for CLI exit-status propagation, GUI
  dispatch, Biometrics GUI keyring creation, and video-command error handling.
  Package-save call sites and fast/slow test registration were inspected
  directly.

- `python tests/run_tests.py --fast` was run on Linux with Python 3.12 in a
  headless environment: 441 tests ran and 47 GUI tests were skipped because no
  display was available; all other tests passed.

Not verified in that environment: the real-KDF slow suite
(`python tests/run_tests.py --slow`) and opening the Tkinter GUI on a physical
display.

### Compatibility and residual risk

- No stored Vault, identity, keyring, biometric-template, attachment, package,
  custody-chain, hardware, or Integrity Ledger format changed. No migration is
  required.

- No BSR2 cryptographic primitive, envelope behavior, authentication policy,
  attempt-limiting behavior, or KDF parameter changed.

- The GUI keyring correction aligns that creation path with the existing POSIX
  sensitive-file behavior; it does not introduce a portable Windows ACL
  mechanism.

- Atomic package writes protect against an interrupted replacement leaving the
  destination partially written, but they do not provide concurrent-writer
  locking.

- The video liveness mechanism remains a motion-presence check rather than
  general anti-spoofing, and the documentation now states that limitation
  explicitly.

- No new external dependencies were introduced. Main remains standard-library
  only outside the deliberately optional, caller-supplied bindings and
  transports used by its hardware subsystem.

---

## [1.9.1] - 2026-09-12

A test-correctness follow-up to 1.9.0.

The unlock-throttling implementation forward-ported from
LTS-2028-SEC-1 and LTS-2028-SEC-2 remained correct. However, the
shared-counter Vault regression test inherited an incomplete correction
from LTS-2028-COR-1.

Version 1.9.0's regression test attempted to expire the ordinary
backoff window by resetting `locked_until` to `0.0`. This was
incorrect. `locked_until` represents the full lockout imposed after the
maximum failed-attempt threshold is reached; ordinary exponential
backoff is calculated using `failed_attempts` and `last_failure_at`.

### Fixed

**Forward-port of `LTS-2028-COR-2` (Low)**

`vault/tests/test_unlock_throttle.py` now preserves
`failed_attempts == 1` while setting `last_failure_at` to `0.0`,
making the recorded failure old enough that the ordinary backoff
interval has elapsed while keeping the shared counter intact.

The corrected test verifies that:

1. A failed passphrase increments the shared persisted counter.
2. The recovery-code path observes the same persisted state.
3. Expiring the ordinary backoff interval does not reset the counter.
4. A valid recovery-code unlock succeeds after the interval has elapsed.
5. Successful recovery-code authentication clears the shared state.

### Verification

The corrected test was validated through the real-KDF slow suite:

