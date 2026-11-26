# Biometrics

Research-grade, local enrollment and verification for voice, fingerprint, and
video samples.

The implementation uses standard-library Python for decoding, feature
extraction, matching, storage, and integration with BSR2. It does not use a
trained biometric model or a cloud recognition service.

## Supported modalities

| Modality | Input | Feature representation |
| --- | --- | --- |
| Voice | Supported PCM WAV files | Mean mel-cepstral coefficients (noise-compensated, gain-independent) and median pitch |
| Fingerprint | Supported PGM or PNG images | Coherence-weighted ridge-orientation field on a 16 x 16 grid |
| Video | BRVID grayscale frame sequences | Illumination-normalised appearance image (24 x 24), temporal median over frames |

Supported input formats are narrower than all possible WAV, PNG, or video
encodings. The codec modules define the accepted variants.

A fixed-length vector makes samples compatible with the matching function.
It does not establish equal recognition quality across different resolutions,
recording durations, devices, or capture conditions.

## Matching

Each modality owns its comparison in its feature module, because the three
templates have different shapes:

- Voice: Euclidean distance between the cepstral and pitch vectors, mapped
  through `exp(-distance / scale)`.
- Fingerprint: the probe's ridge-flow field is rotated (a full circle) and
  shifted to best align with the enrolled field, and the coherence-weighted
  agreement of ridge directions is returned.
- Video: the two appearance images are slid over each other by a few cells and
  the smallest root-mean-square difference is mapped through
  `exp(-distance / scale)`.

Scores are similarity measurements, not identity probabilities or confidence
levels calibrated against a real-world population.

Default acceptance thresholds come from
`biometrics/engine/modalities.py`. Each module's score mapping was calibrated
so that the default threshold sits near a 1% impostor-acceptance point on
synthetic development data; that calibration must be repeated on the real
capture device before the thresholds are relied upon. The extractors and
modality registry are authoritative for current vector dimensions and
thresholds.

Malformed, non-finite, or evidence-free templates score 0.0. Verification
rejects thresholds outside (0, 1].

Templates enrolled with an earlier extractor have a different length.
Verification reports that the stored template cannot be compared and asks for
that modality to be enrolled again.

## Fingerprint template

Fingerprint extraction resizes input to the dimensions defined in
`biometrics/features/fingerprint_features.py`:

- `TARGET_WIDTH = 128`
- `TARGET_HEIGHT = 128`
- `GRID_SIZE = 16` (8 x 8 pixel blocks).
- Two values per grid cell: `(cos 2t, sin 2t)` of the ridge orientation `t`,
  scaled by how coherent the ridges are there.
- Feature-vector length: 512.

The template stores ridge flow only; it does not detect minutiae, so it
separates fingers by their overall pattern and is weaker for fingers of the
same pattern class with similar layouts.

`biometrics/config/settings.py` also defines `TEMPLATE_WIDTH`,
`TEMPLATE_HEIGHT`, `GRID_SIZE`, and `DEFAULT_THRESHOLD` (64x64, 8, 0.94).
Nothing reads them, so changing them has no effect on extraction or matching.

## Voice template

Voice extraction pre-emphasises the recording, cuts it into 32 ms windowed
frames, applies an FFT, subtracts stationary noise measured in the recording's
pauses, pools the spectrum into 24 mel bands, and keeps cepstral coefficients 1
to 12 averaged over the speech frames plus the median pitch. Feature-vector
length: 13. `biometrics/codecs/dsp.py` provides the signal processing.

## Video features and motion checks

Video extraction reduces each sampled frame to 48 x 48, applies gamma
compression, a difference-of-Gaussians band-pass and contrast equalisation so
that lighting and exposure changes largely cancel, pools the result to 24 x 24,
and takes the per-pixel median over the sampled frames:

- 576 appearance values; motion is not part of the template.
- Feature-vector length: 576.

`MAX_FRAMES_SAMPLED` controls frame subsampling separately from vector length.
The supplied extractor samples at most 12 frames for feature extraction.

Enrollment and verification also use a video motion-presence gate unless
`--allow-static` is supplied.

This gate measures frame-to-frame pixel changes and requires localised change
that stands above the clip's sensor noise after overall brightness changes are
removed, so a still photograph with sensor noise or a flickering light does not
count as motion. It is not proof that the capture depicts a live person and is
not general anti-spoofing. Replayed video, moving photographs, synthetic
motion, and other moving inputs are outside what this check can reliably
distinguish. A subject who is completely still for the whole clip, without
blinking or speaking, may be refused.

The default motion threshold has not been calibrated against representative
real-camera data. Voice and fingerprint matching do not provide equivalent
liveness checks.

## BRVID and synthetic video

BRVID is a custom container holding a header and raw grayscale frames. It is
not a general-purpose compressed video format.

The `record-video` CLI command generates a synthetic BRVID sequence. It does
not capture a camera or assemble positional image filenames.

Correct usage:
