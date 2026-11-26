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
| [KI-007](#ki-007-biometrics-gui-can-hide-legitimate-attachment-names) | Biometrics GUI can hide legitimate attachment names | Medium | Open |
| [KI-008](#ki-008-keyring-passphrase-kdf-is-not-memory-hard) | Keyring passphrase KDF is not memory-hard | Medium | Won't fix in 1.3.x; fixed in 1.4.x |
| [KI-009](#ki-009-legacy-v2-envelope-is-not-nonce-misuse-resistant) | Legacy v2 envelope is not nonce-misuse resistant | Low | Won't fix in 1.3.x; fixed in 1.4.x |
| [KI-010](#ki-010-vendored-randomness-lacks-bsr2-alpha-4-hardening) | Vendored randomness lacks BSR2 Alpha 4 hardening | Low | Won't fix in 1.3.x; fixed in 1.4.x |
| [KI-011](#ki-011-deleting-or-replacing-a-vault-bulk-bundle-leaves-its-old-chunk-records-behind) | Deleting or replacing a Vault bulk bundle leaves its old chunk records behind | Medium | Open |
| [KI-012](#ki-012-replacing-a-biometrics-bulk-attachment-with-a-smaller-one-leaves-stale-chunks-behind) | Replacing a Biometrics bulk attachment with a smaller one leaves stale chunks behind | Medium | Open |
| [KI-013](#ki-013-biometric-match-thresholds-are-calibrated-on-synthetic-data-only) | Biometric match thresholds are calibrated on synthetic data only | Medium | Open: needs real-device captures |

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
  mean absolute frame-to-frame pixel difference, plus a coherent-motion check
  that ignores sensor noise and uniform brightness changes) is unit-tested and
  correct against hand-built static, noisy-still, flickering, and moving frame
  sequences — see
  `biometrics/tests/test_liveness.py`. The gap is calibration data, not logic.
  `COHERENT_MOTION_THRESHOLD` (0.005) is equally uncalibrated against real
  cameras.
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
- **Expected behavior:** Chunking permits multiple envelopes to represent
  content larger than the single-envelope payload limit. It does not promise
  unlimited-size or bounded-memory processing.
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
  record's label and kind unchanged when reusing its id.

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

## KI-008: Keyring passphrase KDF is not memory-hard

- **Reported date:** 2026-11-08
- **Severity:** Medium
- **Environment:** All platforms; every LTS-2028 1.3.x keyring (Vault and
  Biometrics).
- **Component:** `crypto/keyring.py`; vendored
  `vendor/brisart_security_primitives.py` (`derive_password_key`)
- **Steps to Reproduce:**
  1. Create a keyring with `Keyring.create(passphrase)`.
  2. Inspect the stored passphrase wrapper: it is derived with BSR2's legacy
     iterated-sponge KDF at 10,000 iterations (`KDF_ITERATIONS`).
- **Expected behavior:** A stolen keyring file should be expensive to attack
  by passphrase guessing on parallel or custom hardware.
- **Actual behavior:** The legacy KDF costs time but no significant memory.
  BSR2's own design documentation lists its lack of
  memory-hardness as a known limitation, which is why BSR2 Alpha 4
  (0.4.0-alpha) added BSR2-MHF-1. Offline guessing against a copied 1.3.x
  keyring is therefore cheaper than against a BSR2-MHF-1 keyring.
- **Tried / Ruled out:** Raising the iteration count (up to
  `MAXIMUM_KDF_ITERATIONS`, 1,000,000) increases cost linearly but does not
  make the KDF memory-hard. A memory-hard KDF would change the stored keyring
  format, which the 1.3.x contract rules out.
- **Next step:** Not fixable within LTS-2028 1.3.x. LTS-2028 1.4.x re-wraps
  keyrings with BSR2-MHF-1 when the operator migrates (1.4.0,
  `LTS-2028-SEC-4`). Until then, use a long
  passphrase and keep keyring files off shared or untrusted storage.

---

## KI-009: Legacy v2 envelope is not nonce-misuse resistant

- **Reported date:** 2026-11-08
- **Severity:** Low
- **Environment:** All platforms; every payload 1.3.x seals (vault records
  and files, biometric templates and attachments, package payloads and key
  slots, keyring wrappers).
- **Component:** `crypto/envelope.py`; vendored
  `vendor/brisart_security_envelope.py`, `vendor/brisart_security_drbg.py`
- **Steps to Reproduce:**
  1. Not reproducible by normal use. The condition requires both the
     operating system's entropy source to repeat its output and the DRBG state
     to be replayed (for example, a VM snapshot restored with a broken entropy
     source).
- **Expected behavior:** Two different messages sealed under the same key
  should never share a keystream, even if randomness fails.
- **Actual behavior:** The v2 envelope (`BSR2-ARX-SPONGE-ETM`) mixes DRBG
  output with fresh OS entropy for its salt and nonce, which covers a DRBG
  restart alone. If both are replayed, two messages can be sealed under the
  same keystream. BSR2 Alpha 4 (0.4.0-alpha) closed this for its v3
  formats and records it as unchanged for the v2 envelope.
- **Tried / Ruled out:** Already reduced by the OS-entropy mixing; the
  remaining case needs two simultaneous failures. Replacing the envelope is a
  stored-format change, which the 1.3.x contract rules out.
- **Next step:** Not fixable within LTS-2028 1.3.x. LTS-2028 1.4.x seals new
  and migrated data in sealed format v3 (`BSR2-S64-SIV`), which is nonce-misuse
  resistant (1.4.0, `LTS-2028-SEC-5`).

---

## KI-010: Vendored randomness lacks BSR2 Alpha 4 hardening

- **Reported date:** 2026-11-08
- **Severity:** Low
- **Environment:** All platforms; affects code that forks a process, or
  copies or pickles a generator, while a DRBG is in use.
- **Component:** `crypto/rng.py`; vendored `vendor/brisart_security_drbg.py`,
  `vendor/brisart_security_entropy.py`
- **Steps to Reproduce:**
  1. Compare the vendored BSR2 Alpha 3 (0.3.0-alpha) `brisart_security_drbg.py`
     and `brisart_security_entropy.py` with `97_Encryption/Official`.
- **Expected behavior:** A DRBG copied into a forked child, or duplicated by
  `copy` or `pickle`, should refuse to produce output, and the entropy source
  should reject a constant sample.
- **Actual behavior:** The vendored BSR2 Alpha 3 copies have none of the
  hardening added in BSR2 Alpha 4 (0.4.0-alpha): no fork detection, no
  refusal of `copy`, `deepcopy`, or `pickle`, and no constant-sample
  rejection. A duplicated generator state would repeat its output.
- **Tried / Ruled out:** No 1.3.x application code outside the tests forks a
  process or uses `multiprocessing` or `subprocess`, so the shipped tools do
  not reach the fork case. Code that embeds 1.3.x modules can.
- **Next step:** Not fixable within LTS-2028 1.3.x without changing the
  byte-pinned vendor files. LTS-2028 1.4.x takes its randomness from BSR2
  Alpha 4, which has this hardening (1.4.0, `LTS-2028-SEC-6`).

---

## KI-011: Deleting or replacing a Vault bulk bundle leaves its old chunk records behind

- **Reported date:** 2026-11-23
- **Severity:** Medium (correctness; data retention)
- **Environment:** LTS-2028 1.3.x, LTS-2028 1.4.x, and Official; all
  platforms. Vault bulk bundles (`encrypt-paths`, the desktop Files tab, and
  `BulkFileService`).
- **Component:** `vault/store/bulk_file_service.py`,
  `vault/store/vault_service.py`, `vault/app.py`, `gui/tabs/tab_vault.py`
- **Steps to Reproduce:**
  1. Create a bulk bundle, for example `BulkFileService(service,
     chunk_bytes=256).upsert_large_bytes("big", <768 random bytes>)`. The
     vault now holds 4 records: one `bundle-manifest` and three
     `bundle-chunk`.
  2. Store a new bundle under the same record id:
     `upsert_large_bytes("big", b"tiny", record_id=<manifest id>)`. The vault
     now holds 5 records: the three old chunks are still there.
  3. Delete the manifest with `VaultService.delete()`, which is what
     `python cli.py vault delete <id>` calls. The vault still holds 4
     records, all `bundle-chunk`.
- **Expected behavior:** Replacing a bundle replaces its chunk records, and
  deleting a bundle's manifest deletes the chunk records that belong to it.
- **Actual behavior:** Chunk records are never deleted by either operation.
  They stay in `vault.json`, still sealed under the master key and still
  decryptable by anyone who unlocks the vault, after the user has deleted or
  replaced the bundle. The vault file grows with each replacement.
  `python cli.py vault list` shows the leftovers as `[bundle-chunk]`. The
  desktop interface cannot delete a bundle at all: its Delete button works on
  the Records sub-tab, which does not list file, bundle-manifest, or
  bundle-chunk records, and the Files sub-tab has no delete action.
- **Tried / Ruled out:** Reproduced on all three lines through the service
  API with 256-byte chunks. Restoring the replacement bundle returns the new
  content, so this is a retention fault and not a data-corruption one.
  `command_delete()` in `vault/app.py` and the Files and Records sub-tabs in
  `gui/tabs/tab_vault.py` were read, not run end to end;
  `VaultService.delete()` removes only the one record it is given.
- **Next step:** Add a bundle-aware delete to `BulkFileService` that reads the
  manifest and removes its chunk records, route `vault delete` for a
  `bundle-manifest` through it, and have `upsert_large_bytes()` remove the
  previous bundle's chunks after the replacement is stored. A delete action on
  the desktop Files sub-tab would be a new feature, so it belongs in Official
  only; LTS-2028 takes no new features. Until then,
  before deleting a bundle run `python cli.py vault get <manifest id>`, delete
  each id in its `chunk_record_ids` first, and then delete the manifest.
  Chunks left by an earlier delete appear in `python cli.py vault list` as
  `[bundle-chunk]` records labelled `<bundle label> (part N)`; delete them by
  id.

---

## KI-012: Replacing a Biometrics bulk attachment with a smaller one leaves stale chunks behind

- **Reported date:** 2026-11-23
- **Severity:** Medium (correctness; data retention)
- **Environment:** LTS-2028 1.3.x, LTS-2028 1.4.x, and Official; all
  platforms. Biometrics bulk attachments (`attach-paths`, the desktop
  Attachments panel, and `attach_large_bytes()`).
- **Component:** `biometrics/engine/bulk_attachments.py`,
  `biometrics/app.py`, `gui/tabs/tab_biometrics.py`
- **Steps to Reproduce:**
  1. Attach a bundle that needs four chunks, for example
     `attach_large_bytes(record, "doc", <1,024 random bytes>, master_key,
     chunk_bytes=256)`. The record holds `doc.chunk0` to `doc.chunk3` and
     `doc.manifest`.
  2. Attach `b"tiny"` under the same name `"doc"`. The record still holds
     `doc.chunk0` to `doc.chunk3` and `doc.manifest`; `doc.chunk1` to
     `doc.chunk3` are left over from step 1. Restoring `"doc"` returns the
     new content.
  3. Call `remove_bulk_attachment(record, "doc", master_key)`, which is what
     `biometrics remove-attachment` and the desktop Remove button use. The
     record still holds `doc.chunk1` to `doc.chunk3`.
- **Expected behavior:** Replacing a bundle leaves only the new bundle's
  chunks, and removing a bundle leaves none of its attachments in the record.
- **Actual behavior:** The new manifest lists only the new chunks, and
  removal deletes only the chunks the current manifest lists, so the older
  `<name>.chunkN` attachments are never deleted. They stay in the identity
  record, sealed under the master key, after the user has replaced and then
  removed the bundle. The desktop interface hides every attachment whose name
  contains `.chunk` (KI-007), so they cannot be seen there; `biometrics inspect`
  lists them.
- **Tried / Ruled out:** Reproduced on all three lines through the attachment
  API with 256-byte chunks. Replacing with a bundle of the same size or larger
  leaves nothing behind, because every old chunk name is overwritten. The
  `attach-paths` command and the desktop panel call the same functions; they
  were read and not run end to end.
- **Next step:** Have `attach_large_bytes()` remove the previous bundle's chunk
  attachments, taken from the old manifest, once the new bundle has been
  attached. Until then, run `python cli.py biometrics remove-attachment
  <identity id> <name>` before attaching a new bundle under the same name.
  Stale chunks left by an earlier replacement can be removed one at a time
  with `python cli.py biometrics remove-attachment <identity id>
  <name>.chunkN`, which removes a single named attachment.

---

## KI-013: Biometric match thresholds are calibrated on synthetic data only

- **Reported date:** 2026-11-26
- **Severity:** Medium
- **Environment:** LTS-2028 1.3.x, LTS-2028 1.4.x, and Official; all platforms.
  The `voice`, `fingerprint`, and `video` biometric modalities.
- **Component:** `biometrics/features/voice_features.py`,
  `biometrics/features/fingerprint_features.py`,
  `biometrics/features/video_features.py`, `biometrics/engine/modalities.py`
- **Steps to Reproduce:**
  1. Enroll a person with real device captures: a microphone recording, a
     fingerprint scanner image, and a camera clip.
  2. Verify the same person on a different day, then verify other people against
     that enrollment, and record the scores `verify_modality()` returns.
  3. Compare the rates at which the right person is rejected and the wrong
     person is accepted with the intended operating point.
- **Expected behavior:** The default thresholds (voice 0.85, fingerprint 0.80,
  video 0.75) give a low false-acceptance rate and an acceptable
  false-rejection rate on the capture devices actually in use.
- **Actual behavior:** Unknown. The score mappings (`DISTANCE_SCALE` in the
  voice and video modules, `SCORE_POWER` in the fingerprint module) were set so
  that each default threshold sits at about a 1% impostor-acceptance rate on
  synthetic development data: generated voices, ridge patterns, and drawn
  faces. Those constants were checked on a separate set of synthetic subjects
  during development, which is not part of the release. The figures do not
  transfer to real people or devices. Known weaknesses of the current design:
  the voice template is a single averaged vector, so different spoken content,
  very short recordings, and a different microphone move it; the fingerprint
  template stores ridge flow only and has no minutiae, so it separates fingers
  by overall pattern; the video template is an appearance image, not a face
  model, and needs consistent framing.
- **Tried / Ruled out:** The extractors and matchers are covered by
  deterministic tests (`test_voice_features.py`, `test_fingerprint_features.py`,
  `test_video_features.py`). They show the code behaves as designed on
  generated inputs. They say nothing about real-world error rates.
- **Next step:** Collect real captures from the capture devices in use, from
  several people over several sessions. Re-derive `DISTANCE_SCALE` and
  `SCORE_POWER` from them, then set the thresholds in
  `biometrics/engine/modalities.py`. Until then treat biometric verification as
  a convenience check, not as strong authentication.

---

## Template

Use this template for new entries:
