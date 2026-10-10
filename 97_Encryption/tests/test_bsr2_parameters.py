"""
File: tests/test_bsr2_parameters.py

Purpose
-------
Reproducibility checks for the committed BSR2 fixed parameters.

Communication / relationships
-----------------------------
Direct module imports: unittest, brisart_security_primitives, tools.generate_bsr2_parameters.

Settings / parameters
---------------------
No uppercase module-level settings are declared; parameters remain defined in the code below.

Edge cases
----------
Additional edge-case guarantees are not established by this header; existing implementation and tests remain unchanged.

Known limitations
-----------------
This header update does not establish complete behavioral, platform, or security validation.

Examples
--------
Run this test file with the project-scoped test runner.
"""

import unittest

from brisart_security_primitives import (
    BSR2_PARAMETER_SEED,
    INITIAL_STATE_CONSTANT,
    LANE_INDEX_CONSTANT,
    ROTATIONS,
    ROUND_CONSTANTS,
    ROUND_INDEX_CONSTANT,
    WORD_PERMUTATION,
)
from tools.generate_bsr2_parameters import PARAMETER_SEED, generate_parameters


class BSR2ParameterTests(unittest.TestCase):
    def test_public_seed_matches(self) -> None:
        self.assertEqual(BSR2_PARAMETER_SEED, PARAMETER_SEED.decode("ascii"))

    def test_generated_parameters_match_embedded_values(self) -> None:
        parameters = generate_parameters()
        structural = parameters["structural_constants"]

        self.assertEqual(tuple(parameters["round_constants"]), ROUND_CONSTANTS)
        self.assertEqual(tuple(parameters["rotations"]), ROTATIONS)
        self.assertEqual(
            tuple(parameters["word_permutation"]),
            WORD_PERMUTATION,
        )
        self.assertEqual(structural[0], ROUND_INDEX_CONSTANT)
        self.assertEqual(structural[1], LANE_INDEX_CONSTANT)
        self.assertEqual(structural[2], INITIAL_STATE_CONSTANT)

    def test_parameter_shapes(self) -> None:
        self.assertEqual(len(ROUND_CONSTANTS), 24)
        self.assertEqual(len(set(ROUND_CONSTANTS)), 24)
        self.assertTrue(all(value != 0 for value in ROUND_CONSTANTS))

        self.assertEqual(len(ROTATIONS), 8)
        self.assertEqual(len(set(ROTATIONS)), 8)
        self.assertTrue(all(1 <= value <= 63 for value in ROTATIONS))

        self.assertEqual(sorted(WORD_PERMUTATION), list(range(16)))


if __name__ == "__main__":
    unittest.main(verbosity=2)

