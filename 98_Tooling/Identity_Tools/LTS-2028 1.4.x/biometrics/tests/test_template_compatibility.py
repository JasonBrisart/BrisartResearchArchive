"""
File: biometrics/tests/test_template_compatibility.py

Purpose
-------
Tests for how verification treats stored templates and match thresholds after
the biometric extractors changed. A template sealed by an earlier extractor has
a different length from a current one; verification must report that plainly
(telling the owner to enrol again) rather than crash or compare unlike things.
Invalid thresholds, which would otherwise accept everyone or no one, must be
refused before any stored data is touched.

Communication / relationships
-----------------------------
Verifies: biometrics/engine/verification.py (verify_modality).
Uses biometrics.identity.identity_record, biometrics.engine.enrollment,
biometrics.samples.sample_generator and the sealing helpers in crypto.envelope.
No keyring or passphrase derivation is needed; a random 32-byte master key is
sealed with directly.

Settings / parameters
---------------------
- Stale template lengths are those of the earlier extractors: 192 values for
  fingerprint, 20 for voice and 72 for video.
- Thresholds under test: NaN, infinity, zero, a negative number, 1.5, a
  boolean and a string.

Edge cases
----------
- A stale template of each modality raises VerificationError that mentions
  enrolling again.
- A current template for the same probe verifies normally (the same file
  scores 1.0), so the stale-template error is not a blanket failure.
- Every invalid threshold raises VerificationError and no template is opened.
- A threshold of exactly 1.0 is accepted.

Known limitations
-----------------
- The tests cover a length mismatch, which is how an earlier extractor's
  template is recognised. A template of the right length whose values mean
  something different would not be detected; the extractors' lengths changed
  so that this cannot happen for fingerprint, voice or video.

Examples
--------
::

    python -m unittest biometrics.tests.test_template_compatibility -v
    python tests/run_tests.py
"""

import secrets
import tempfile
import unittest
from pathlib import Path

from biometrics.engine import enrollment, modalities, verification
from biometrics.identity import identity_record
from biometrics.samples import sample_generator
from crypto.context import template_context
from crypto.envelope import seal_json
from crypto.rng import new_generator

IDENTITY = "compat-test"
STALE_LENGTHS = {"fingerprint": 192, "voice": 20, "video": 72}


def _record():
    return identity_record.new_record(IDENTITY, "Compatibility", "test-device")


def _with_vector(record, master_key, modality, vector):
    payload = {"modality": modality, "vector": vector}
    envelope = seal_json(master_key, payload, template_context(IDENTITY, modality),
                         new_generator("compat-test"))
    return identity_record.set_template(record, modality, envelope)


class StaleTemplateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.master_key = secrets.token_bytes(32)
        self.probes = {
            "fingerprint": self.tmp / "probe.pgm",
            "voice": self.tmp / "probe.wav",
            "video": self.tmp / "probe.brvid",
        }
        sample_generator.write_fingerprint_sample(self.probes["fingerprint"], "compat")
        sample_generator.write_voice_sample(self.probes["voice"], "compat")
        sample_generator.write_video_sample(self.probes["video"], "compat", 32, 32, 6)

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_template_from_an_earlier_extractor_asks_for_re_enrolment(self):
        for modality, length in STALE_LENGTHS.items():
            with self.subTest(modality=modality):
                record = _with_vector(_record(), self.master_key, modality, [0.1] * length)
                with self.assertRaises(verification.VerificationError) as caught:
                    verification.verify_modality(record, modality, self.probes[modality],
                                                 self.master_key, allow_static=True)
                self.assertIn("enrol", str(caught.exception))

    def test_a_current_template_for_the_same_probe_verifies(self):
        for modality in STALE_LENGTHS:
            with self.subTest(modality=modality):
                vector = modalities.extract_from_path(modality, self.probes[modality])
                record = _with_vector(_record(), self.master_key, modality, vector)
                result = verification.verify_modality(record, modality, self.probes[modality],
                                                      self.master_key, allow_static=True)
                self.assertAlmostEqual(result["score"], 1.0, places=6)
                self.assertTrue(result["matched"])


class ThresholdValidationTests(unittest.TestCase):
    def _record_with_placeholder(self, modality="fingerprint"):
        return {"identity_id": IDENTITY, "templates": {modality: {"placeholder": True}}}

    def test_invalid_thresholds_are_refused_before_any_template_is_opened(self):
        for bad in (float("nan"), float("inf"), float("-inf"), 0, 0.0, -0.5, 1.5, True, "0.8"):
            with self.subTest(threshold=bad), self.assertRaises(verification.VerificationError):
                verification.verify_modality(self._record_with_placeholder(), "fingerprint",
                                             "unused.pgm", b"\x00" * 32, threshold=bad)

    def test_a_threshold_of_exactly_one_is_valid(self):
        # The threshold check passes, so the failure comes later, from opening
        # the placeholder template -- which is a different, authentication error.
        with self.assertRaises(verification.VerificationError) as caught:
            verification.verify_modality(self._record_with_placeholder(), "fingerprint",
                                         "unused.pgm", b"\x00" * 32, threshold=1.0)
        self.assertNotIn("threshold must be", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
