# Biometrics

Research-grade, local enrollment and verification for voice, fingerprint, and
video samples.

The implementation uses standard-library Python for decoding, feature
extraction, matching, storage, and integration with BSR2. It does not use a
trained biometric model or a cloud recognition service.

## Supported modalities

| Modality | Input | Feature representation |
| --- | --- | --- |
| Voice | Supported PCM WAV files | Averaged frame-level energy, zero-crossing, and DCT-based summary features |
| Fingerprint | Supported PGM or PNG images | Grid-based orientation and gradient-magnitude features |
| Video | BRVID grayscale frame sequences | Spatial block means and frame-difference motion summaries |

Supported input formats are narrower than all possible WAV, PNG, or video
encodings. The codec modules define the accepted variants.

A fixed-length vector makes samples compatible with the matching function.
It does not establish equal recognition quality across different resolutions,
recording durations, devices, or capture conditions.

## Matching

Each modality uses `distance_similarity()` from
`biometrics/features/similarity.py`, a normalized Euclidean-distance score.

Scores are similarity measurements, not identity probabilities or confidence
levels calibrated against a real-world population.

Default acceptance thresholds come from
`biometrics/engine/modalities.py`. The extractors and modality registry are
authoritative for current vector dimensions and thresholds.

Historical before-and-after scores in the changelog refer to particular
fixtures and releases. They are not general accuracy guarantees.

## Fingerprint geometry

Fingerprint extraction resizes input to the dimensions defined in
`biometrics/features/fingerprint_features.py`:

- `TARGET_WIDTH = 128`
- `TARGET_HEIGHT = 128`
- `GRID_SIZE = 8`
- Three values per grid cell.
- Feature-vector length: 192.

`biometrics/config/settings.py` also defines `TEMPLATE_WIDTH`,
`TEMPLATE_HEIGHT`, `GRID_SIZE`, and `DEFAULT_THRESHOLD` (64x64, 8, 0.94).
Nothing reads them, so changing them has no effect on extraction or matching.

## Video features and motion checks

Video extraction uses a 6-by-6 grid:

- 36 spatial-summary values.
- 36 motion-summary values.
- Total feature-vector length: 72.

`MAX_FRAMES_SAMPLED` controls frame subsampling separately from vector length.
The supplied extractor samples at most 60 frames for feature extraction.

Enrollment and verification also use a video motion-presence gate unless
`--allow-static` is supplied.

This gate measures frame-to-frame pixel changes. It is not proof that the
capture depicts a live person and is not general anti-spoofing. Replayed video,
moving photographs, synthetic motion, and other moving inputs are outside
what this check can reliably distinguish.

The default motion threshold has not been calibrated against representative
real-camera data. Voice and fingerprint matching do not provide equivalent
liveness checks.

## BRVID and synthetic video

BRVID is a custom container holding a header and raw grayscale frames. It is
not a general-purpose compressed video format.

The `record-video` CLI command generates a synthetic BRVID sequence. It does
not capture a camera or assemble positional image filenames.

Correct usage:

```bash
python cli.py biometrics record-video clip.brvid --seed my-seed --frames 12 --frame-rate 12
python cli.py biometrics probe-video clip.brvid
```

Different seeds can change generated parameters, but distinct seeds do not
guarantee distinct feature vectors or visible motion. Some generated video
parameters can produce zero drift.

## CLI usage

Run these commands from the selected application root, containing `cli.py`.

```bash
python cli.py biometrics --help

# Generate deterministic synthetic samples.
python cli.py biometrics make-samples my-seed --output-dir data/samples

# Enroll using generated voice and fingerprint samples.
python cli.py biometrics enroll alice --label "Alice" \
  --voice data/samples/my-seed_voice.wav \
  --fingerprint data/samples/my-seed_fingerprint.pgm

# Verify one modality.
python cli.py biometrics verify alice --voice data/samples/my-seed_voice.wav

# Require all supplied modalities to match.
python cli.py biometrics verify alice \
  --voice data/samples/my-seed_voice.wav \
  --fingerprint data/samples/my-seed_fingerprint.pgm

# Accept any one supplied modality.
python cli.py biometrics verify alice \
  --voice data/samples/my-seed_voice.wav \
  --fingerprint data/samples/my-seed_fingerprint.pgm \
  --any-match

# Inspect public metadata.
python cli.py biometrics inspect alice
python cli.py biometrics list

# Delete an identity.
python cli.py biometrics delete alice
```

For video enrollment:

```bash
python cli.py biometrics enroll video-demo --label "Video Demo" --video clip.brvid
python cli.py biometrics verify video-demo --video clip.brvid
```

A static synthetic clip can be rejected by the motion gate. `--allow-static`
explicitly bypasses that gate; it does not make the input a live capture.

```bash
python cli.py biometrics enroll static-demo --label "Static Demo" \
  --video clip.brvid --allow-static

python cli.py biometrics verify static-demo --video clip.brvid --allow-static
```

Re-enrollment of an existing identity is refused. There is no overwrite flag.
Deleting an identity before replacement also removes its stored identity state;
it is not an in-place template update.

## Storage and keyring

Identity records contain readable metadata such as the identity identifier,
label, and enrolled modalities.

Template payloads are sealed under a local master key. A keyring wraps that
master key under a passphrase-derived key and an offline recovery-code-derived
key.

Operations that need the master key load or create the keyring and prompt for
the required secret material. Creating a new keyring displays its recovery
code once.

The CLI and GUI use the shared passphrase-unlock path in
`biometrics/identity/keyring_access.py`, including persisted attempt limiting.

Attempt state is stored in the keyring JSON. It is not protection against an
attacker who can copy or edit that file and perform offline guesses.

POSIX file-mode hardening is best effort. Windows access control requires
appropriate filesystem permissions outside these POSIX mode checks.

Device binding records a keyed value derived from machine information. It is
a weak additional check, not hardware-backed identity or an independent
security boundary.

## Reports

`biometrics/reports/report_writer.py` writes separate JSON files for enrollment
and verification events.

Verification reports retain:

- Identity identifier and event metadata.
- Overall match outcome.
- Per-modality name, similarity score, threshold, and match outcome.

They do not retain feature vectors or sealed template bytes.

They also do not retain the complete video motion/liveness result, including
its motion energy and gate details. A stored report therefore cannot fully
reconstruct why a video gate passed or failed.

New-file-per-event writing is append-style behavior, not an enforced
append-only or authenticated audit store. A party with filesystem write access
can alter or remove reports.

## Attachments

Arbitrary file bytes can be attached to an identity. Bulk attachments use
chunks and a manifest.

See [file and bundle encryption](../docs/FILE_AND_BUNDLE_ENCRYPTION.md) for memory,
temporary-file, throughput, and restore limitations.

## Module map

- `app.py`: CLI parsing and command orchestration.
- `codecs/`: supported image, audio, and BRVID decoding.
- `features/`: extraction, similarity, and video motion checks.
- `engine/`: enrollment, verification, modality dispatch, and attachments.
- `identity/`: record validation, storage, device binding, and keyring access.
- `reports/`: report construction and persistence.
- `samples/`: deterministic synthetic samples.
- `tests/`: regression tests for the supplied application components.

## Security status

This is a research implementation, not production biometric authentication.

BSR2 is unreviewed research cryptography. Matching thresholds and motion
checks are not substitutes for independently validated authentication controls.

See [BSR2 integration and threat model](../docs/BSR2_INTEGRATION.md) and
../docs/KNOWN_ISSUES.md.
