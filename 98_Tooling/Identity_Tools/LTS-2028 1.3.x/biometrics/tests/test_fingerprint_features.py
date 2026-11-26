"""
File: biometrics/tests/test_fingerprint_features.py

Purpose
-------
Tests for biometrics/features/fingerprint_features.py. The tests draw small
ridge patterns (whorl-like swirls with a chosen ridge spacing and centre) with
the standard library, then check what the extractor and matcher are for: the
same print stays close when it is rotated, shifted, noisy, faint or
re-contrasted, different prints stay apart, and unusable images are refused.

Communication / relationships
-----------------------------
Verifies: biometrics/features/fingerprint_features.py.
Uses biometrics.engine.modalities for the default threshold and the project's
sample generator for one end-to-end check. Standard library only otherwise.

Settings / parameters
---------------------
- SIZE = 128 pixels square, the extractor's analysis resolution.
- Print A: a swirl with ridge spacing 0.55 rad/pixel and centre (58, 66).
  Print B: wavy parallel ridges (an arch) with spacing 0.5, a different pattern
  type.
- The default fingerprint threshold, 0.80, comes from
  biometrics.engine.modalities.default_threshold("fingerprint").

Edge cases
----------
- The same print rotated by 25, 90 and 180 degrees, shifted by 12 pixels, with
  noise, at one third contrast, and after a gain/offset change scores above the
  default threshold.
- A different print scores below it, in the original and in rotated form.
- Flat, nearly flat and ridge-free (random noise) images are refused with
  FingerprintFeatureError, as are bad dimensions and a wrong-sized buffer.
- A template of another length (an earlier extractor's) is detected.
- Non-finite and all-zero templates score 0.0.

Known limitations
-----------------
- The prints are synthetic ridge patterns, not impressions of fingers; passing
  shows the matcher behaves sensibly, not that it recognises real people.
- Fingers of the same pattern class with similar layouts are deliberately not
  asserted: the matcher compares ridge flow and cannot separate two swirls that
  differ only by where their centre sits (a shift it tolerates). The benchmark
  measures that case.

Examples
--------
::

    python -m unittest biometrics.tests.test_fingerprint_features -v
    python tests/run_tests.py
"""

import math
import random
import unittest

from biometrics.engine import modalities
from biometrics.features import fingerprint_features as fp
from biometrics.samples import sample_generator

SIZE = 128


def _print(spacing, centre, order, phase=0.0):
    """A swirl of ridges: sin(spacing * radius + order * angle + phase)."""
    pixels = bytearray(SIZE * SIZE)
    for row in range(SIZE):
        for col in range(SIZE):
            radius = math.hypot(col - centre[0], row - centre[1])
            angle = math.atan2(row - centre[1], col - centre[0])
            value = math.sin(spacing * radius + order * angle + phase)
            pixels[row * SIZE + col] = int(127.5 + 100.0 * value)
    return bytes(pixels)


def _arch(spacing, bend, phase=0.0):
    """Wavy parallel ridges: a different pattern type from the swirl."""
    pixels = bytearray(SIZE * SIZE)
    for row in range(SIZE):
        for col in range(SIZE):
            value = math.sin(spacing * (row - bend * math.sin(col * 0.045)) + phase)
            pixels[row * SIZE + col] = int(127.5 + 100.0 * value)
    return bytes(pixels)


def _rotate(pixels, degrees):
    phi = math.radians(degrees)
    cos, sin = math.cos(phi), math.sin(phi)
    centre = (SIZE - 1) / 2.0
    out = bytearray(SIZE * SIZE)
    for row in range(SIZE):
        for col in range(SIZE):
            x, y = col - centre, row - centre
            src_x = int(round(cos * x + sin * y + centre))
            src_y = int(round(-sin * x + cos * y + centre))
            if 0 <= src_x < SIZE and 0 <= src_y < SIZE:
                out[row * SIZE + col] = pixels[src_y * SIZE + src_x]
            else:
                out[row * SIZE + col] = 127
    return bytes(out)


def _shift(pixels, dx, dy):
    out = bytearray([127] * (SIZE * SIZE))
    for row in range(SIZE):
        for col in range(SIZE):
            src_x, src_y = col - dx, row - dy
            if 0 <= src_x < SIZE and 0 <= src_y < SIZE:
                out[row * SIZE + col] = pixels[src_y * SIZE + src_x]
    return bytes(out)


def _noisy(pixels, sigma, seed=3):
    rng = random.Random(seed)
    return bytes(max(0, min(255, int(v + rng.gauss(0, sigma)))) for v in pixels)


def _recontrast(pixels, gain, offset):
    return bytes(max(0, min(255, int(127 + (v - 127) * gain + offset))) for v in pixels)


class FingerprintMatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.threshold = modalities.default_threshold("fingerprint")
        cls.print_a = _print(0.55, (58, 66), 2)
        cls.print_b = _arch(0.5, 14.0)
        cls.template_a = fp.extract_from_pixels(SIZE, SIZE, cls.print_a)
        cls.template_b = fp.extract_from_pixels(SIZE, SIZE, cls.print_b)

    def _template(self, pixels):
        return fp.extract_from_pixels(SIZE, SIZE, pixels)

    def test_template_has_the_documented_length_and_range(self):
        self.assertEqual(len(self.template_a), fp.FEATURE_VECTOR_LENGTH)
        self.assertTrue(all(-1.0 <= value <= 1.0 for value in self.template_a))

    def test_identical_templates_score_one(self):
        self.assertAlmostEqual(fp.compare(self.template_a, self.template_a), 1.0, places=9)

    def test_rotated_prints_still_match(self):
        for degrees in (25, 90, 180):
            with self.subTest(degrees=degrees):
                probe = self._template(_rotate(self.print_a, degrees))
                self.assertGreater(fp.compare(self.template_a, probe), self.threshold)

    def test_shifted_print_still_matches(self):
        probe = self._template(_shift(self.print_a, 12, -9))
        self.assertGreater(fp.compare(self.template_a, probe), self.threshold)

    def test_noisy_print_still_matches(self):
        probe = self._template(_noisy(self.print_a, 28.0))
        self.assertGreater(fp.compare(self.template_a, probe), self.threshold)

    def test_faint_and_re_contrasted_prints_still_match(self):
        for gain, offset in ((0.33, 0), (1.0, 40), (0.6, -30)):
            with self.subTest(gain=gain, offset=offset):
                probe = self._template(_recontrast(self.print_a, gain, offset))
                self.assertGreater(fp.compare(self.template_a, probe), self.threshold)

    def test_a_different_print_does_not_match(self):
        self.assertLess(fp.compare(self.template_a, self.template_b), self.threshold)
        rotated_b = self._template(_rotate(self.print_b, 40))
        self.assertLess(fp.compare(self.template_a, rotated_b), self.threshold)

    def test_matching_prints_score_well_above_different_prints(self):
        genuine = fp.compare(self.template_a, self._template(_rotate(self.print_a, 15)))
        impostor = fp.compare(self.template_a, self.template_b)
        self.assertGreater(genuine, impostor + 0.3)

    def test_generator_prints_of_one_seed_match_and_of_two_seeds_do_not(self):
        from biometrics.codecs import pgm
        decoded = pgm.decode(sample_generator.generate_fingerprint_image("ci-enroll"))
        other = pgm.decode(sample_generator.generate_fingerprint_image("ci-other"))
        a = fp.extract_from_pixels(decoded["width"], decoded["height"], decoded["pixels"])
        b = fp.extract_from_pixels(other["width"], other["height"], other["pixels"])
        self.assertAlmostEqual(fp.compare(a, a), 1.0, places=9)
        self.assertLess(fp.compare(a, b), 1.0)


class FingerprintInputValidationTests(unittest.TestCase):
    def test_flat_and_nearly_flat_images_are_refused(self):
        with self.assertRaises(fp.FingerprintFeatureError):
            fp.extract_from_pixels(SIZE, SIZE, bytes([90] * (SIZE * SIZE)))
        nearly_flat = bytes(90 + (i % 3) for i in range(SIZE * SIZE))
        with self.assertRaises(fp.FingerprintFeatureError):
            fp.extract_from_pixels(SIZE, SIZE, nearly_flat)

    def test_random_noise_without_ridges_is_refused(self):
        rng = random.Random(9)
        noise = bytes(rng.randrange(60, 200) for _ in range(SIZE * SIZE))
        with self.assertRaises(fp.FingerprintFeatureError):
            fp.extract_from_pixels(SIZE, SIZE, noise)

    def test_bad_dimensions_and_buffers_are_refused(self):
        for width, height in ((0, 8), (8, -1), (8.0, 8), (True, 8)):
            with self.subTest(width=width, height=height), self.assertRaises(fp.FingerprintFeatureError):
                fp.extract_from_pixels(width, height, bytes(64))
        with self.assertRaises(fp.FingerprintFeatureError):
            fp.extract_from_pixels(8, 8, bytes(63))

    def test_template_from_an_earlier_extractor_is_detected_by_length(self):
        with self.assertRaises(fp.FingerprintFeatureError):
            fp.compare([0.5] * 192, [0.5] * fp.FEATURE_VECTOR_LENGTH)

    def test_non_finite_and_all_zero_templates_score_zero(self):
        good = [0.5, 0.2] * (fp.FEATURE_VECTOR_LENGTH // 2)
        bad = list(good)
        bad[10] = float("inf")
        self.assertEqual(fp.compare(good, bad), 0.0)
        self.assertEqual(fp.compare([0.0] * fp.FEATURE_VECTOR_LENGTH, good), 0.0)


if __name__ == "__main__":
    unittest.main()
