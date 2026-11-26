"""
File: biometrics/tests/test_video_features.py

Purpose
-------
Tests for biometrics/features/video_features.py. The tests render small
grayscale "scenes" (a head-like oval with eyes, a nose and a mouth) with the
standard library, then check what the extractor is for: the same scene stays
close when the lighting, exposure, noise or framing changes or a few frames
are corrupted, different scenes stay apart, and unusable clips are refused.

Communication / relationships
-----------------------------
Verifies: biometrics/features/video_features.py.
Uses biometrics.engine.modalities for the default threshold. Standard library
only otherwise.

Settings / parameters
---------------------
- SIZE = 64 pixel square frames, 8 frames per clip.
- Scene A: eyes 12 pixels either side of centre, mouth width 16. Scene B: eyes
  19 pixels either side of centre and lower, mouth width 26, a darker face.
- The default video threshold, 0.75, comes from
  biometrics.engine.modalities.default_threshold("video").
- Scenes are chosen to be clearly different. Look-alike scenes with the same
  overall layout can score above the threshold; the benchmark, not this unit
  test, measures how often.

Edge cases
----------
- The same scene with a gain change, an additive offset, a strong left-to-right
  lighting ramp, noise, a two-pixel shift, or a few corrupted frames scores
  above the default threshold.
- A different scene scores below it, including under a lighting change.
- Uniform (blank) frames are refused with VideoFeatureError; a clip with only
  some blank frames is accepted from the frames that have detail.
- A single frame and frames smaller than the 48 pixel analysis size work.
- Bad dimensions, an empty clip and a wrong-sized frame are refused.
- A template of another length (an earlier extractor's) is detected.
- Non-finite templates score 0.0.

Known limitations
-----------------
- The scenes are synthetic drawings, not faces; passing shows the extractor
  behaves sensibly, not that it recognises real people.

Examples
--------
::

    python -m unittest biometrics.tests.test_video_features -v
    python tests/run_tests.py
"""

import math
import random
import unittest

from biometrics.engine import modalities
from biometrics.features import video_features as vf
from biometrics.samples import sample_generator

SIZE = 64
FRAMES = 8


def _scene(eye_dx, eye_y, mouth_w, skin, sway=0.0):
    """A head-like oval with eyes, a nose and a mouth on a darker background."""
    pixels = bytearray(SIZE * SIZE)
    for row in range(SIZE):
        for col in range(SIZE):
            x, y = (col - SIZE / 2 - sway) / (SIZE / 2), (row - SIZE / 2) / (SIZE / 2)
            value = 40 + (skin - 40) * math.exp(-((x / 0.7) ** 2 + (y / 0.9) ** 2) * 1.8)
            for sign in (-1, 1):
                ex = sign * eye_dx / (SIZE / 2)
                value -= 60 * math.exp(-(((x - ex) / 0.07) ** 2 + ((y - eye_y) / 0.04) ** 2))
            value -= 25 * math.exp(-((x / 0.05) ** 2 + ((y - 0.05) / 0.16) ** 2))
            value -= 55 * math.exp(-((x / (mouth_w / (SIZE / 2) / 2)) ** 2 + ((y - 0.38) / 0.04) ** 2))
            pixels[row * SIZE + col] = max(0, min(255, int(value)))
    return bytes(pixels)


def _clip(frame, count=FRAMES):
    return [frame] * count


def _lit(frame, gain=1.0, offset=0.0, ramp=0.0):
    out = bytearray(len(frame))
    for index, value in enumerate(frame):
        col = index % SIZE
        shade = 1.0 + ramp * (col / SIZE - 0.5) * 2.0
        out[index] = max(0, min(255, int(value * gain * shade + offset)))
    return bytes(out)


def _noisy(frame, sigma, seed):
    rng = random.Random(seed)
    return bytes(max(0, min(255, int(v + rng.gauss(0, sigma)))) for v in frame)


class VideoMatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.threshold = modalities.default_threshold("video")
        cls.scene_a = _scene(12, -0.12, 16, 180)
        cls.scene_b = _scene(19, 0.02, 26, 150)
        cls.template_a = vf.extract_from_frames(SIZE, SIZE, _clip(cls.scene_a))
        cls.template_b = vf.extract_from_frames(SIZE, SIZE, _clip(cls.scene_b))

    def _template(self, frames):
        return vf.extract_from_frames(SIZE, SIZE, frames)

    def test_template_has_the_documented_length_and_range(self):
        self.assertEqual(len(self.template_a), vf.FEATURE_VECTOR_LENGTH)
        self.assertTrue(all(-1.0 <= value <= 1.0 for value in self.template_a))

    def test_identical_templates_score_one(self):
        self.assertAlmostEqual(vf.compare(self.template_a, self.template_a), 1.0, places=9)

    def test_lighting_and_exposure_changes_still_match(self):
        for name, frame in (
            ("half gain", _lit(self.scene_a, gain=0.5)),
            ("offset", _lit(self.scene_a, offset=45)),
            ("left-to-right ramp", _lit(self.scene_a, ramp=0.6)),
            ("ramp and gain", _lit(self.scene_a, gain=0.7, ramp=-0.5)),
        ):
            with self.subTest(change=name):
                self.assertGreater(vf.compare(self.template_a, self._template(_clip(frame))),
                                   self.threshold)

    def test_sensor_noise_still_matches(self):
        frames = [_noisy(self.scene_a, 14.0, seed) for seed in range(FRAMES)]
        self.assertGreater(vf.compare(self.template_a, self._template(frames)), self.threshold)

    def test_small_shift_in_framing_still_matches(self):
        shifted = _scene(12, -0.12, 16, 180, sway=2.0)
        self.assertGreater(vf.compare(self.template_a, self._template(_clip(shifted))),
                           self.threshold)

    def test_corrupted_frames_are_outvoted_by_the_median(self):
        frames = _clip(self.scene_a)
        frames[2] = bytes([255] * (SIZE * SIZE))
        frames[3] = bytes([0] * (SIZE * SIZE))
        self.assertGreater(vf.compare(self.template_a, self._template(frames)), self.threshold)

    def test_a_different_scene_does_not_match(self):
        self.assertLess(vf.compare(self.template_a, self.template_b), self.threshold)
        relit = self._template(_clip(_lit(self.scene_b, gain=0.6, ramp=0.5)))
        self.assertLess(vf.compare(self.template_a, relit), self.threshold)

    def test_same_scene_scores_well_above_a_different_scene(self):
        genuine = vf.compare(self.template_a,
                             self._template(_clip(_lit(self.scene_a, gain=0.6, ramp=0.4))))
        impostor = vf.compare(self.template_a, self.template_b)
        self.assertGreater(genuine, impostor + 0.15)

    def test_extraction_is_deterministic(self):
        self.assertEqual(self._template(_clip(self.scene_a)), self.template_a)


class VideoInputTests(unittest.TestCase):
    def test_uniform_frames_are_refused(self):
        with self.assertRaises(vf.VideoFeatureError):
            vf.extract_from_frames(SIZE, SIZE, _clip(bytes([100] * (SIZE * SIZE))))

    def test_blank_frames_among_good_ones_do_not_block_extraction(self):
        good = _scene(12, -0.12, 16, 180)
        frames = [bytes([0] * (SIZE * SIZE)), good, good, bytes([0] * (SIZE * SIZE))]
        self.assertEqual(len(vf.extract_from_frames(SIZE, SIZE, frames)),
                         vf.FEATURE_VECTOR_LENGTH)

    def test_single_frame_and_small_frames_work(self):
        self.assertEqual(len(vf.extract_from_frames(SIZE, SIZE, [_scene(12, -0.12, 16, 180)])),
                         vf.FEATURE_VECTOR_LENGTH)
        small = bytes((row * 7 + col * 13) % 200 for row in range(16) for col in range(16))
        self.assertEqual(len(vf.extract_from_frames(16, 16, [small, small])),
                         vf.FEATURE_VECTOR_LENGTH)

    def test_bad_dimensions_empty_clips_and_wrong_sized_frames_are_refused(self):
        frame = _scene(12, -0.12, 16, 180)
        for width, height in ((0, SIZE), (SIZE, -3), (SIZE + 0.0, SIZE), (True, SIZE)):
            with self.subTest(width=width, height=height), self.assertRaises(vf.VideoFeatureError):
                vf.extract_from_frames(width, height, [frame])
        with self.assertRaises(vf.VideoFeatureError):
            vf.extract_from_frames(SIZE, SIZE, [])
        with self.assertRaises(vf.VideoFeatureError):
            vf.extract_from_frames(SIZE, SIZE, [frame, frame[:-1]])

    def test_long_clips_are_subsampled_not_rejected(self):
        frame = _scene(12, -0.12, 16, 180)
        long_clip = [frame] * (vf.MAX_FRAMES_SAMPLED * 3 + 1)
        self.assertEqual(len(vf.extract_from_frames(SIZE, SIZE, long_clip)),
                         vf.FEATURE_VECTOR_LENGTH)

    def test_generator_clips_of_one_seed_match_and_of_two_seeds_differ(self):
        a = sample_generator.generate_video_frames("ci-enroll", 32, 32, 6)
        b = sample_generator.generate_video_frames("ci-other", 32, 32, 6)
        ta = vf.extract_from_frames(32, 32, a)
        tb = vf.extract_from_frames(32, 32, b)
        self.assertAlmostEqual(vf.compare(ta, ta), 1.0, places=9)
        self.assertLess(vf.compare(ta, tb), 1.0)

    def test_template_from_an_earlier_extractor_is_detected_by_length(self):
        with self.assertRaises(vf.VideoFeatureError):
            vf.compare([0.1] * 72, [0.1] * vf.FEATURE_VECTOR_LENGTH)

    def test_non_finite_templates_score_zero(self):
        good = [0.2] * vf.FEATURE_VECTOR_LENGTH
        bad = list(good)
        bad[5] = float("nan")
        self.assertEqual(vf.compare(good, bad), 0.0)


if __name__ == "__main__":
    unittest.main()
