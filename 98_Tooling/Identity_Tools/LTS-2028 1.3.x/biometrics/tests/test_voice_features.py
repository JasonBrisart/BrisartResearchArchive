"""
File: biometrics/tests/test_voice_features.py

Purpose
-------
Tests for biometrics/features/voice_features.py and the FFT, filterbank and
pitch primitives in biometrics/codecs/dsp.py that it relies on. The tests
build small source-filter "voices" (a harmonic source shaped by vowel-like
resonances, with pauses) from the standard library, so they check what the
extractor is for: the same speaker stays close across recordings, different
speakers stay apart, and recording gain, noise and unusable audio are
handled.

Communication / relationships
-----------------------------
Verifies: biometrics/features/voice_features.py, biometrics/codecs/dsp.py
(fft, power_spectrum, mel_filterbank, apply_filterbank, estimate_pitch) and
the voice generator in biometrics/samples/sample_generator.py.
Uses only the standard library and the project's own modules.

Settings / parameters
---------------------
- SAMPLE_RATE = 8000 Hz; each synthetic recording is about 1.6 seconds.
- Speaker A: 110 Hz pitch, formant scale 1.00. Speaker B: 210 Hz pitch,
  formant scale 1.15.
- The default voice threshold, 0.85, comes from
  biometrics.engine.modalities.default_threshold("voice").

Edge cases
----------
- Same speaker, different recording and phrase, scores above the default
  threshold.
- A different speaker scores below the default threshold.
- Recording gain (a 5x quieter copy) leaves the template unchanged.
- Moderate noise (15 dB) keeps the same speaker closer than a different one.
- A sustained tone with no pauses is accepted, not erased by noise removal.
- Silence, constant, empty, non-finite, boolean, too-short, too-low-rate and
  unvoiced (white-noise) input is refused with VoiceFeatureError.
- A template of another length (an earlier extractor's) is detected.
- The demo voice generator produces sound for its whole duration.

Known limitations
-----------------
- The voices are synthetic; passing shows the extractor behaves sensibly, not
  that it recognises real people. See the voice_features.py header.
- Pitch and formant values are chosen to be easy to separate.

Examples
--------
::

    python -m unittest biometrics.tests.test_voice_features -v
    python tests/run_tests.py
"""

import math
import random
import unittest

from biometrics.codecs import dsp
from biometrics.engine import modalities
from biometrics.features import voice_features
from biometrics.samples import sample_generator

SAMPLE_RATE = 8000
_VOWELS = ((730, 1090, 2440), (270, 2290, 3010), (570, 840, 2410), (530, 1840, 2480))


def _voice(pitch, scale, seed, gain=1.0, noise_db=None, seconds=1.6, pauses=True):
    """A harmonic source shaped by vowel-like resonances, with short pauses."""
    rng = random.Random(seed)
    samples = []
    syllables = max(1, int(seconds / 0.27))
    for index in range(syllables):
        formants = _VOWELS[(index + seed) % len(_VOWELS)]
        f0 = pitch * (1.0 + rng.uniform(-0.03, 0.03))
        count = int(0.2 * SAMPLE_RATE)
        harmonics = [(h * f0, 1.0 / (1.0 + sum(
            ((h * f0 - f * scale) / 90.0) ** 2 for f in formants) * 0.05))
            for h in range(1, int(3500 / f0) + 1)]
        for n in range(count):
            t = n / SAMPLE_RATE
            envelope = min(1.0, n / 120.0, (count - n) / 120.0)
            samples.append(envelope * sum(a * math.sin(2 * math.pi * f * t)
                                          for f, a in harmonics))
        if pauses:
            samples.extend([0.0] * int(0.07 * SAMPLE_RATE))
    peak = max(abs(v) for v in samples) or 1.0
    samples = [v / peak * 8000.0 for v in samples]
    if noise_db is not None:
        power = sum(v * v for v in samples) / len(samples)
        sigma = math.sqrt(power / (10.0 ** (noise_db / 10.0)))
        samples = [v + rng.gauss(0.0, sigma) for v in samples]
    return [int(round(v * gain)) for v in samples]


class VoiceFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a1 = voice_features.extract_from_samples(_voice(110, 1.00, 1), SAMPLE_RATE)
        cls.a2 = voice_features.extract_from_samples(_voice(110, 1.00, 2), SAMPLE_RATE)
        cls.a_quiet = voice_features.extract_from_samples(
            _voice(110, 1.00, 1, gain=0.2), SAMPLE_RATE)
        cls.a_noisy = voice_features.extract_from_samples(
            _voice(110, 1.00, 2, noise_db=15), SAMPLE_RATE)
        cls.b1 = voice_features.extract_from_samples(_voice(210, 1.15, 3), SAMPLE_RATE)
        cls.threshold = modalities.default_threshold("voice")

    def test_template_has_the_documented_length_and_is_finite(self):
        self.assertEqual(len(self.a1), voice_features.FEATURE_VECTOR_LENGTH)
        self.assertTrue(all(math.isfinite(value) for value in self.a1))

    def test_identical_templates_score_one(self):
        self.assertEqual(voice_features.compare(self.a1, self.a1), 1.0)

    def test_same_speaker_scores_above_the_default_threshold(self):
        self.assertGreater(voice_features.compare(self.a1, self.a2), self.threshold)

    def test_different_speaker_scores_below_the_default_threshold(self):
        self.assertLess(voice_features.compare(self.a1, self.b1), self.threshold)

    def test_same_speaker_is_closer_than_a_different_speaker(self):
        self.assertGreater(voice_features.compare(self.a1, self.a2),
                           voice_features.compare(self.a1, self.b1) + 0.2)

    def test_recording_gain_does_not_change_the_template(self):
        self.assertGreater(voice_features.compare(self.a1, self.a_quiet), 0.99)

    def test_moderate_noise_keeps_the_same_speaker_closer(self):
        self.assertGreater(voice_features.compare(self.a1, self.a_noisy),
                           voice_features.compare(self.a1, self.b1))

    def test_sustained_tone_without_pauses_is_accepted(self):
        tone = _voice(130, 1.0, 5, pauses=False)
        self.assertEqual(len(voice_features.extract_from_samples(tone, SAMPLE_RATE)),
                         voice_features.FEATURE_VECTOR_LENGTH)

    def test_float_samples_are_accepted(self):
        samples = [float(v) for v in _voice(110, 1.0, 1)]
        self.assertEqual(voice_features.extract_from_samples(samples, SAMPLE_RATE), self.a1)


class VoiceInputValidationTests(unittest.TestCase):
    def _assert_refused(self, samples, rate=SAMPLE_RATE):
        with self.assertRaises(voice_features.VoiceFeatureError):
            voice_features.extract_from_samples(samples, rate)

    def test_empty_silent_and_constant_recordings_are_refused(self):
        self._assert_refused([])
        self._assert_refused([0] * 4000)
        self._assert_refused([500] * 4000)

    def test_non_finite_and_non_numeric_samples_are_refused(self):
        good = _voice(110, 1.0, 1)
        for bad in (float("nan"), float("inf"), "x", True, None):
            with self.subTest(bad=bad):
                self._assert_refused(good[:2000] + [bad] + good[2000:])

    def test_bad_sample_rates_are_refused(self):
        good = _voice(110, 1.0, 1)
        for rate in (0, -8000, 8000.0, True, 1000, "8000"):
            with self.subTest(rate=rate):
                self._assert_refused(good, rate)

    def test_recording_too_short_to_analyse_is_refused(self):
        self._assert_refused(_voice(110, 1.0, 1)[:300])

    def test_unvoiced_noise_is_refused(self):
        rng = random.Random(4)
        self._assert_refused([int(rng.gauss(0, 3000)) for _ in range(12000)])

    def test_template_from_an_earlier_extractor_is_detected_by_length(self):
        with self.assertRaises(voice_features.VoiceFeatureError):
            voice_features.compare([0.1] * 20, [0.1] * voice_features.FEATURE_VECTOR_LENGTH)

    def test_non_finite_template_values_score_zero(self):
        good = [0.5] * voice_features.FEATURE_VECTOR_LENGTH
        bad = list(good)
        bad[3] = float("nan")
        self.assertEqual(voice_features.compare(good, bad), 0.0)


class SampleGeneratorVoiceTests(unittest.TestCase):
    def test_generated_voice_is_sound_for_its_whole_duration(self):
        generated = sample_generator.generate_voice_sample("regression-seed")
        samples = generated["samples"]
        last_second = samples[-generated["sample_rate"]:]
        self.assertGreater(max(abs(v) for v in last_second), 1000)

    def test_generated_voices_of_different_seeds_are_told_apart(self):
        first = sample_generator.generate_voice_sample("ci-enroll")
        other = sample_generator.generate_voice_sample("ci-other")
        a = voice_features.extract_from_samples(first["samples"], first["sample_rate"])
        b = voice_features.extract_from_samples(other["samples"], other["sample_rate"])
        self.assertEqual(voice_features.compare(a, a), 1.0)
        self.assertLess(voice_features.compare(a, b), modalities.default_threshold("voice"))


class DspPrimitiveTests(unittest.TestCase):
    def test_fft_matches_the_definition_of_the_dft(self):
        rng = random.Random(1)
        values = [rng.uniform(-1, 1) for _ in range(32)]
        real, imag = dsp.fft(values)
        for k in (0, 1, 5, 17):
            expected_real = sum(v * math.cos(2 * math.pi * k * n / 32) for n, v in enumerate(values))
            expected_imag = -sum(v * math.sin(2 * math.pi * k * n / 32) for n, v in enumerate(values))
            self.assertAlmostEqual(real[k], expected_real, places=9)
            self.assertAlmostEqual(imag[k], expected_imag, places=9)

    def test_fft_rejects_lengths_that_are_not_a_power_of_two(self):
        with self.assertRaises(dsp.DspError):
            dsp.fft([1.0, 2.0, 3.0])

    def test_power_spectrum_peaks_at_the_tone_frequency(self):
        tone = [math.sin(2 * math.pi * 1000 * n / SAMPLE_RATE) for n in range(256)]
        spectrum = dsp.power_spectrum(tone, 256)
        peak_bin = max(range(len(spectrum)), key=spectrum.__getitem__)
        self.assertEqual(peak_bin, round(1000 / (SAMPLE_RATE / 256)))

    def test_pitch_of_a_harmonic_tone_is_found_and_noise_is_unvoiced(self):
        tone = [math.sin(2 * math.pi * 125 * n / SAMPLE_RATE)
                + 0.4 * math.sin(2 * math.pi * 250 * n / SAMPLE_RATE) for n in range(256)]
        self.assertAlmostEqual(dsp.estimate_pitch(tone, SAMPLE_RATE), 125.0, delta=4.0)
        rng = random.Random(2)
        self.assertEqual(dsp.estimate_pitch([rng.gauss(0, 1) for _ in range(256)], SAMPLE_RATE), 0.0)

    def test_mel_filterbank_covers_the_requested_band_with_triangles(self):
        bank = dsp.mel_filterbank(10, 256, SAMPLE_RATE, 100.0, 3800.0)
        self.assertEqual(len(bank), 10)
        for first, weights in bank:
            self.assertTrue(max(weights) > 0.0)
            self.assertTrue(all(0.0 <= w <= 1.0 for w in weights))
        flat = [1.0] * 129
        energies = dsp.apply_filterbank(flat, bank)
        self.assertTrue(all(e > 0 for e in energies))


if __name__ == "__main__":
    unittest.main()
