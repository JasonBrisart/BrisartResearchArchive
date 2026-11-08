"""
File: biometrics/tests/test_multimodal_flow.py

Purpose
-------
Tests for multimodal enrollment and verification (voice + fingerprint + video
together), including require_all vs. any-match semantics.

Verifies: biometrics/engine/enrollment.py, biometrics/engine/verification.py,
biometrics/samples/sample_generator.py, biometrics/identity/identity_record.py.
Contains 7 test case(s) across 1 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- biometrics.engine.enrollment (biometrics/engine/enrollment.py)
- biometrics.engine.verification (biometrics/engine/verification.py)
- biometrics.samples.sample_generator (biometrics/samples/sample_generator.py)
- biometrics.identity.identity_record (biometrics/identity/identity_record.py)
Standard library: pathlib, secrets, tempfile, unittest.
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
No module-level settings. Each test builds its own isolated fixtures (temporary
directories, freshly generated keys) in setUp and removes them afterwards, so
tests are order-independent and never touch real data/ folders.

Edge cases
----------
- All three modalities enrolled.
- Verify all three matches with same samples.
- Require all fails if one modality has no template.
- Any match true if at least one modality matches.
- Verify identity requires at least one probe source.
- Enroll identity requires at least one modality source.
- Verify modality raises for unenrolled modality.

Known limitations
-----------------
- Passing proves only the 7 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
::

    python -m unittest biometrics.tests.test_multimodal_flow -v
    python tests/run_tests.py
"""

import secrets
import tempfile
import unittest
from pathlib import Path

from biometrics.engine import enrollment, verification
from biometrics.samples import sample_generator


class MultimodalFlowTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp_dir.name)
        self.master_key = secrets.token_bytes(32)

        self.voice_path = self.tmp_path / "voice.wav"
        self.fingerprint_path = self.tmp_path / "fingerprint.pgm"
        self.video_path = self.tmp_path / "video.brvid"
        sample_generator.write_voice_sample(self.voice_path, "seed-voice")
        sample_generator.write_fingerprint_sample(self.fingerprint_path, "seed-print")
        sample_generator.write_video_sample(self.video_path, "seed-video", width=16, height=16, frame_count=6)

        self.record = enrollment.enroll_identity(
            "multi-id",
            "Multimodal Example",
            self.master_key,
            {
                "voice": self.voice_path,
                "fingerprint": self.fingerprint_path,
                "video": self.video_path,
            },
        )

    def tearDown(self):
        self._tmp_dir.cleanup()

    def test_all_three_modalities_enrolled(self):
        from biometrics.identity.identity_record import enrolled_modalities
        self.assertEqual(
            enrolled_modalities(self.record), ["fingerprint", "video", "voice"]
        )

    def test_verify_all_three_matches_with_same_samples(self):
        result = verification.verify_identity(
            self.record,
            {
                "voice": self.voice_path,
                "fingerprint": self.fingerprint_path,
                "video": self.video_path,
            },
            self.master_key,
            require_all=True,
        )
        self.assertTrue(result["matched"])
        self.assertEqual(len(result["results"]), 3)

    def test_require_all_fails_if_one_modality_has_no_template(self):
        with self.assertRaises(verification.VerificationError):
            verification.verify_identity(
                self.record,
                {"voice": self.voice_path, "fingerprint": self.fingerprint_path,
                 "video": self.video_path,
                 "nonexistent_field_not_a_real_modality": self.voice_path},
                self.master_key,
            )

    def test_any_match_true_if_at_least_one_modality_matches(self):
        result = verification.verify_identity(
            self.record,
            {"fingerprint": self.fingerprint_path},
            self.master_key,
            require_all=False,
        )
        self.assertTrue(result["matched"])

    def test_verify_identity_requires_at_least_one_probe_source(self):
        with self.assertRaises(verification.VerificationError):
            verification.verify_identity(self.record, {}, self.master_key)

    def test_enroll_identity_requires_at_least_one_modality_source(self):
        with self.assertRaises(enrollment.EnrollmentError):
            enrollment.enroll_identity("no-modalities", "Label", self.master_key, {})

    def test_verify_modality_raises_for_unenrolled_modality(self):
        bare_record = enrollment.create_identity("bare", "Bare Example", self.master_key)
        with self.assertRaises(verification.VerificationError):
            verification.verify_modality(
                bare_record, "voice", self.voice_path, self.master_key
            )


if __name__ == "__main__":
    unittest.main()




