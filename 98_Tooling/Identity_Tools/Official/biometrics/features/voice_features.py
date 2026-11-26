"""
File: biometrics/features/voice_features.py

Purpose
-------
Turn a mono voice recording into a fixed-length speaker feature vector and
score how closely two such vectors resemble each other.

Public interface:
- class VoiceFeatureError(ValueError) -- Raised when a recording or a feature
  vector cannot be processed.
- extract_from_samples(samples, sample_rate) -- Feature vector from mono
  samples (signed integers or floats).
- extract_from_wav(path) -- Decode a WAV file with ``wave_tools`` and extract.
- compare(vector_a, vector_b) -- Similarity in (0.0, 1.0] between two vectors.
- FEATURE_VECTOR_LENGTH -- Number of values in every voice template.

The extractor is a conventional cepstral speaker front end built only from the
standard library. Each recording is pre-emphasised, cut into 32 ms Hamming
windowed frames (50% overlap), and converted to a power spectrum with the FFT
in ``biometrics.codecs.dsp``. Stationary background noise is estimated from
the quietest frames and, when the recording contains pauses to measure it in,
subtracted from every spectrum before the spectra are pooled into 24
mel-scale filterbank bands. The log band energies are decorrelated
with a DCT, and cepstral coefficients 1 to 12 are averaged over the speech
frames. Coefficient 0 (overall level) is discarded, so recording gain does
not change the template. A thirteenth value carries the speaker's median
fundamental frequency (pitch), measured on voiced frames by autocorrelation.

Frames that fall below one tenth of the loudest noise-compensated frame are
treated as pauses and ignored, and each band is floored at 3% of its own peak
so that bands buried in noise take the same value in a clean and a noisy
recording of the same speaker.

compare() measures the Euclidean distance between two templates and maps it
through exp(-distance / DISTANCE_SCALE), so identical templates score exactly
1.0 and the score falls smoothly toward 0.0 as the voices diverge. The scale
is chosen so that the package's default voice threshold (0.85, see
biometrics/engine/modalities.py) sits at roughly a 1% impostor-acceptance
operating point on the development recordings the front end was tuned on.

Communication / relationships
-----------------------------
Depends on (project modules):
- biometrics.codecs.dsp (windowing, energy, FFT, mel filterbank, DCT, pitch
  estimation)
- biometrics.codecs.wave_tools (WAV decoding)
Standard library: math.
Imported by:
- biometrics/engine/modalities.py (registers extract_from_wav and compare)
Covered by tests: biometrics/tests/test_voice_features.py,
biometrics/tests/test_multimodal_flow.py,
biometrics/tests/test_sealed_biometrics_flow.py.

Settings / parameters
---------------------
- FRAME_SECONDS = 0.032 -- Analysis frame length; the FFT size is the next
  power of two of FRAME_SECONDS * sample_rate (at least 128).
- PRE_EMPHASIS = 0.97 -- First-order high-frequency boost applied first.
- FILTER_COUNT = 24 / LOW_HZ = 100 / HIGH_FRACTION = 0.95 -- Mel filterbank
  size and span (the upper edge is 95% of the Nyquist frequency).
- CEPSTRUM_COUNT = 12 -- Cepstral coefficients kept (1 to 12).
- NOISE_FRACTION = 0.15 / NOISE_OVER_SUBTRACTION = 3.0 -- Share of quietest
  frames used as the noise estimate and the factor it is scaled by before
  subtraction.
- PAUSE_RATIO = 0.5 -- Noise is subtracted only when the quietest frames carry
  less than this fraction of the median frame energy, i.e. when the recording
  really contains pauses to measure the noise in.
- SPEECH_GATE = 0.1 -- Frames below this fraction of the loudest frame's
  energy are dropped.
- BAND_FLOOR = 0.03 -- Per-band floor, as a fraction of the band's own peak.
- PITCH_WEIGHT = 10.0 -- Weight of log2(pitch / 100 Hz) in the template.
- DISTANCE_SCALE -- Distance that maps to a score of exp(-1).
- MIN_VOICED_FRAMES = 3 / MIN_FRAMES = 4 -- Minimum evidence needed.
- FEATURE_VECTOR_LENGTH = CEPSTRUM_COUNT + 1 = 13

Edge cases
----------
- extract_from_samples() raises VoiceFeatureError: "sample_rate must be a
  positive integer." for a zero, negative, fractional or boolean rate, and
  for a rate below 4000 Hz, which cannot carry usable speech detail.
- extract_from_samples() raises VoiceFeatureError: "samples must not be
  empty." and "samples must contain finite numeric values." for empty input
  and for non-numeric, boolean, NaN or infinite samples.
- extract_from_samples() raises VoiceFeatureError for a recording with no
  varying signal, one that is too short to give MIN_FRAMES analysis frames,
  or one with fewer than MIN_VOICED_FRAMES voiced frames. Silence and
  noise-only audio therefore cannot be enrolled as a voice.
- compare() raises VoiceFeatureError: "feature vectors must be the same
  length." when the lengths differ, which is how a template created by an
  earlier extractor is detected; the owner must re-enrol. Vectors of the
  right length that contain non-finite values score 0.0.

Known limitations
-----------------
- The template is a single averaged vector, so it describes a speaker's
  typical spectrum rather than the sequence of sounds. Different spoken
  content shifts the average, and short recordings (about one second) are
  markedly less reliable than recordings of two seconds or more.
- Pitch is informative but varies with emotion, health and speaking effort.
- Spectral subtraction assumes stationary noise and at least a few quiet
  frames. Music, crosstalk and continuous speech without pauses are not
  compensated (the subtraction is skipped when there are no pauses, so a
  sustained tone or unbroken speech is not erased).
- A convolutive channel (a different microphone or a telephone line) adds a
  constant to the cepstrum and moves the template. Enrol on the capture
  device that will be used for verification.
- This is not a trained speaker-embedding model. It does not detect replayed
  or synthesised speech.
- DISTANCE_SCALE was calibrated on synthetic development recordings. It must
  be re-checked against recordings from the real capture device before the
  default threshold is relied upon.

Examples
--------
Call shapes only, not a runnable script: samples and path stand for values
the caller supplies.

::

    from biometrics.features.voice_features import (
        extract_from_samples,
        extract_from_wav,
        compare,
    )
    template = extract_from_samples(samples, 8000)
    probe = extract_from_wav(path)
    score = compare(template, probe)
"""
import math

from biometrics.codecs import dsp, wave_tools

FRAME_SECONDS = 0.032
PRE_EMPHASIS = 0.97
FILTER_COUNT = 24
LOW_HZ = 100.0
HIGH_FRACTION = 0.95
CEPSTRUM_COUNT = 12
NOISE_FRACTION = 0.15
NOISE_OVER_SUBTRACTION = 3.0
PAUSE_RATIO = 0.5
SPEECH_GATE = 0.1
BAND_FLOOR = 0.03
PITCH_WEIGHT = 10.0
DISTANCE_SCALE = 25.0
MIN_SAMPLE_RATE = 4000
MIN_VOICED_FRAMES = 3
MIN_FRAMES = 4
# cepstral coefficients 1..CEPSTRUM_COUNT + median pitch
FEATURE_VECTOR_LENGTH = CEPSTRUM_COUNT + 1


class VoiceFeatureError(ValueError):
    """Raised when voice feature extraction or comparison cannot proceed."""


def _validate(samples: list, sample_rate: int) -> None:
    if (isinstance(sample_rate, bool) or not isinstance(sample_rate, int)
            or sample_rate < MIN_SAMPLE_RATE):
        raise VoiceFeatureError("sample_rate must be a positive integer.")
    if len(samples) == 0:
        raise VoiceFeatureError("samples must not be empty.")
    for value in samples:
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value)):
            raise VoiceFeatureError("samples must contain finite numeric values.")


def _cepstrum(log_bands: list) -> list:
    """Cepstral coefficients 1..CEPSTRUM_COUNT of log band energies.

    ``dsp.discrete_cosine_transform`` is the unnormalised DCT-II; the factor
    sqrt(2 / bands) makes it orthonormal, so coefficients keep a comparable
    scale whatever the filterbank size.
    """
    scale = math.sqrt(2.0 / len(log_bands))
    return [scale * value
            for value in dsp.discrete_cosine_transform(log_bands, CEPSTRUM_COUNT + 1)[1:]]


def extract_from_samples(samples: list, sample_rate: int) -> list:
    """Extract the fixed-length speaker feature vector from mono samples."""
    _validate(samples, sample_rate)
    if max(samples) == min(samples):
        raise VoiceFeatureError("recording contains no varying audio signal.")
    frame_size = max(128, dsp.next_power_of_two(int(FRAME_SECONDS * sample_rate)))
    hop = frame_size // 2
    values = [float(value) for value in samples]
    emphasised = [values[0]] + [values[i] - PRE_EMPHASIS * values[i - 1]
                                for i in range(1, len(values))]
    starts = list(range(0, len(values) - frame_size + 1, hop))
    if len(starts) < MIN_FRAMES:
        raise VoiceFeatureError("recording is too short to analyse.")
    spectra, energies = [], []
    for start in starts:
        frame = emphasised[start:start + frame_size]
        spectra.append(dsp.power_spectrum(dsp.apply_hamming_window(frame), frame_size))
        energies.append(dsp.short_time_energy(frame))
    if max(energies) <= 0:
        raise VoiceFeatureError("recording has insufficient signal energy.")

    # Stationary-noise estimate from the quietest frames, then subtraction.
    quiet = sorted(range(len(energies)), key=energies.__getitem__)
    quiet = quiet[:max(2, int(NOISE_FRACTION * len(quiet)))]
    bins = len(spectra[0])
    noise = [sum(spectra[i][b] for i in quiet) / len(quiet) for b in range(bins)]
    median_energy = sorted(energies)[len(energies) // 2]
    if sum(energies[i] for i in quiet) / len(quiet) >= PAUSE_RATIO * median_energy:
        noise = [0.0] * bins   # no pauses, so there is nothing to measure noise in
    cleaned = [[max(row[b] - NOISE_OVER_SUBTRACTION * noise[b], 0.0)
                for b in range(bins)] for row in spectra]
    cleaned_energy = [sum(row) for row in cleaned]
    loudest = max(cleaned_energy)
    if loudest <= 0:
        raise VoiceFeatureError("recording has insufficient signal energy.")
    keep = [i for i, e in enumerate(cleaned_energy) if e >= SPEECH_GATE * loudest]
    if len(keep) < MIN_FRAMES:
        keep = sorted(sorted(range(len(cleaned_energy)),
                             key=cleaned_energy.__getitem__)[-MIN_FRAMES:])

    bank = dsp.mel_filterbank(FILTER_COUNT, frame_size, sample_rate, LOW_HZ,
                              HIGH_FRACTION * sample_rate / 2.0)
    bands = [dsp.apply_filterbank(cleaned[i], bank) for i in keep]
    peaks = [max(frame[b] for frame in bands) for b in range(FILTER_COUNT)]
    floors = [max(BAND_FLOOR * peak, 1e-12) for peak in peaks]
    cepstra = [_cepstrum([math.log(max(frame[b], floors[b]))
                          for b in range(FILTER_COUNT)]) for frame in bands]
    mean = [sum(frame[k] for frame in cepstra) / len(cepstra)
            for k in range(CEPSTRUM_COUNT)]

    pitches = []
    for i in keep:
        pitch = dsp.estimate_pitch(values[starts[i]:starts[i] + frame_size], sample_rate)
        if pitch > 0:
            pitches.append(pitch)
    if len(pitches) < MIN_VOICED_FRAMES:
        raise VoiceFeatureError("recording contains too little voiced speech.")
    pitches.sort()
    median_pitch = pitches[len(pitches) // 2]
    return mean + [PITCH_WEIGHT * math.log2(median_pitch / 100.0)]


def extract_from_wav(path) -> list:
    """Read a WAV file and extract its fixed-length voice feature vector."""
    decoded = wave_tools.read_wave(path)
    return extract_from_samples(decoded["samples"], decoded["sample_rate"])


def compare(vector_a: list, vector_b: list) -> float:
    """Similarity in (0.0, 1.0] between two voice feature vectors.

    exp(-d / DISTANCE_SCALE) of the Euclidean distance d; identical vectors
    score exactly 1.0. Malformed or non-finite vectors score 0.0, so they can
    never produce a match.
    """
    if len(vector_a) != len(vector_b):
        raise VoiceFeatureError("feature vectors must be the same length.")
    if not vector_a:
        return 0.0
    try:
        a = [float(v) for v in vector_a]
        b = [float(v) for v in vector_b]
    except (TypeError, ValueError, OverflowError):
        return 0.0
    if not all(math.isfinite(v) for v in a + b):
        return 0.0
    return math.exp(-math.dist(a, b) / DISTANCE_SCALE)
