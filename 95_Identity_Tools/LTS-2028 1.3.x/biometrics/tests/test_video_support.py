"""
File: biometrics/tests/test_video_support.py

Purpose
-------
Tests for biometrics.codecs.video, biometrics.features.video_features, and the
biometrics CLI's record-video and probe-video commands.

Verifies: biometrics/codecs/video.py, biometrics/features/video_features.py,
biometrics/samples/sample_generator.py, biometrics/app.py.
Contains 17 test case(s) across 3 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- biometrics.codecs.video (biometrics/codecs/video.py)
- biometrics.features.video_features (biometrics/features/video_features.py)
- biometrics.samples.sample_generator (biometrics/samples/sample_generator.py)
- biometrics.app (biometrics/app.py)
Standard library: contextlib, io, pathlib, tempfile, unittest.
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
No module-level settings. Each test builds its own isolated fixtures (temporary
directories, freshly generated keys) inline and removes them afterwards, so
tests are order-independent and never touch real data/ folders.

Edge cases
----------
VideoCodecTests:
- Encode decode round trip.
- Rejects wrong frame size.
- Rejects empty frame list.
- Rejects bad magic.
- Rejects body over ceiling before slicing.
- Probe reports header without reading frames.
- Probe rejects body over ceiling.
VideoFeatureTests:
- Extract from frames returns fixed length vector.
- Single frame has zero motion component.
- Different seeds produce different vectors.
- Compare identical vectors is near one.
- Compare rejects mismatched lengths.
- Extract from video file round trip.
VideoCliTests:
- record-video creates missing parent directories.
- record-video reports an invalid frame count as an error, not a traceback.
- probe-video reports a missing file as an error, not a traceback.
- probe-video reports a non-BRVID file as an error, not a traceback.

Known limitations
-----------------
- Passing proves only the 17 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
::

    python -m unittest biometrics.tests.test_video_support -v
    python tests/run_tests.py
"""

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from biometrics import app as biometrics_app
from biometrics.codecs import video
from biometrics.features import video_features
from biometrics.samples import sample_generator


class VideoCodecTests(unittest.TestCase):
    def test_encode_decode_round_trip(self):
        width, height = 4, 4
        frames = [bytes([value] * (width * height)) for value in (10, 20, 30)]
        encoded = video.encode(width, height, frame_rate=5, frames=frames)
        decoded = video.decode(encoded)
        self.assertEqual(decoded["width"], width)
        self.assertEqual(decoded["height"], height)
        self.assertEqual(decoded["frame_rate"], 5)
        self.assertEqual(decoded["frames"], frames)

    def test_rejects_wrong_frame_size(self):
        with self.assertRaises(video.VideoFormatError):
            video.encode(4, 4, 5, [b"\x00" * 10])

    def test_rejects_empty_frame_list(self):
        with self.assertRaises(video.VideoFormatError):
            video.encode(4, 4, 5, [])

    def test_rejects_bad_magic(self):
        with self.assertRaises(video.VideoFormatError):
            video.decode(b"NOTVIDEO" + b"\x00" * 20)

    def test_rejects_body_over_ceiling_before_slicing(self):
        # Fix 1 (2026-09-09): width, height, and frame_count are each within
        # their individual maxima, but their product implies a body far larger
        # than MAX_BODY_BYTES. decode() must refuse based on the header alone,
        # before attempting to slice a body of that size.
        header = video.HEADER_STRUCT.pack(
            video.MAGIC, video.MAX_DIMENSION, video.MAX_DIMENSION,
            video.MAX_FRAME_COUNT, 5,
        )
        with self.assertRaises(video.VideoFormatError):
            video.decode(header + b"")

    def test_probe_reports_header_without_reading_frames(self):
        width, height = 4, 4
        frames = [bytes([1] * (width * height))]
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "sample.brvid"
            video.write_video(path, width, height, 5, frames)
            info = video.probe(path)
            self.assertEqual(info["width"], width)
            self.assertEqual(info["height"], height)
            self.assertEqual(info["frame_count"], 1)
            self.assertTrue(info["size_matches_header"])

    def test_probe_rejects_body_over_ceiling(self):
        # Fix 2 (2026-09-11): probe() must apply the same
        # frame_count * width * height ceiling decode() already enforces, so
        # a header whose fields are each individually valid but whose
        # product is absurd is refused from the header alone.
        header = video.HEADER_STRUCT.pack(
            video.MAGIC, video.MAX_DIMENSION, video.MAX_DIMENSION,
            video.MAX_FRAME_COUNT, 5,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "hostile.brvid"
            path.write_bytes(header)
            with self.assertRaises(video.VideoFormatError):
                video.probe(path)


class VideoFeatureTests(unittest.TestCase):
    def test_extract_from_frames_returns_fixed_length_vector(self):
        width, height = 12, 12
        frames = sample_generator.generate_video_frames("seed-a", width, height, 5)
        vector = video_features.extract_from_frames(width, height, frames)
        self.assertEqual(len(vector), video_features.FEATURE_VECTOR_LENGTH)

    def test_single_frame_has_zero_motion_component(self):
        width, height = 12, 12
        frames = sample_generator.generate_video_frames("seed-b", width, height, 1)
        vector = video_features.extract_from_frames(width, height, frames)
        motion_half = vector[len(vector) // 2:]
        self.assertTrue(all(value == 0.0 for value in motion_half))

    def test_different_seeds_produce_different_vectors(self):
        width, height = 16, 16
        frames_a = sample_generator.generate_video_frames("seed-a", width, height, 6)
        frames_b = sample_generator.generate_video_frames("seed-z", width, height, 6)
        vector_a = video_features.extract_from_frames(width, height, frames_a)
        vector_b = video_features.extract_from_frames(width, height, frames_b)
        self.assertNotEqual(vector_a, vector_b)

    def test_compare_identical_vectors_is_near_one(self):
        width, height = 12, 12
        frames = sample_generator.generate_video_frames("seed-c", width, height, 5)
        vector = video_features.extract_from_frames(width, height, frames)
        self.assertAlmostEqual(video_features.compare(vector, vector), 1.0, places=6)

    def test_compare_rejects_mismatched_lengths(self):
        with self.assertRaises(video_features.VideoFeatureError):
            video_features.compare([1.0, 2.0], [1.0])

    def test_extract_from_video_file_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "sample.brvid"
            sample_generator.write_video_sample(path, "seed-d", width=16, height=16, frame_count=4)
            vector = video_features.extract_from_video(path)
            self.assertEqual(len(vector), video_features.FEATURE_VECTOR_LENGTH)


class VideoCliTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp_dir.name)

    def tearDown(self):
        self._tmp_dir.cleanup()

    def _run(self, argv):
        stderr = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
            code = biometrics_app.main(argv)
        return code, stderr.getvalue()

    def test_record_video_creates_missing_parent_directories(self):
        output = self.tmp_path / "new" / "nested" / "clip.brvid"
        code, _ = self._run(["record-video", str(output), "--frames", "3"])
        self.assertEqual(code, 0)
        self.assertTrue(output.is_file())

    def test_record_video_invalid_frame_count_is_reported_as_error(self):
        output = self.tmp_path / "clip.brvid"
        code, stderr = self._run(["record-video", str(output), "--frames", "0"])
        self.assertEqual(code, 2)
        self.assertIn("error:", stderr)

    def test_probe_video_missing_file_is_reported_as_error(self):
        code, stderr = self._run(["probe-video", str(self.tmp_path / "missing.brvid")])
        self.assertEqual(code, 2)
        self.assertIn("error:", stderr)

    def test_probe_video_non_brvid_file_is_reported_as_error(self):
        junk = self.tmp_path / "junk.brvid"
        junk.write_bytes(b"not a video")
        code, stderr = self._run(["probe-video", str(junk)])
        self.assertEqual(code, 2)
        self.assertIn("error:", stderr)


if __name__ == "__main__":
    unittest.main()




