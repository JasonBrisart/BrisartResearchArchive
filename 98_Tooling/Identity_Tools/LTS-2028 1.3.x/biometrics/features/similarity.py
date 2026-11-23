"""
File: biometrics/features/similarity.py

Purpose
-------
Shared similarity scoring for biometric feature vectors.

Public interface:
- distance_similarity(vector_a, vector_b) -- Similarity in (0.0, 1.0] based on
  Euclidean distance between two equal-length feature vectors, normalized by
  their own average magnitude and mapped through exponential decay so identical
  vectors score exactly 1.0 and similarity falls off smoothly and boundedly as
  the vectors diverge.

Design notes:

Used by fingerprint_features.py, video_features.py, and voice_features.py so
the scoring logic exists in exactly one place instead of being copied into all
three modality modules.

For these feature spaces -- fingerprint orientation and magnitude values, raw
video pixel-brightness block-means, and voice energy/band-DCT vectors -- two
genuinely different people's vectors still point in a broadly similar direction
(they're mostly positive, similarly shaped data), so cosine reported near-1.0
"matches" between impostors.

Confirmed directly against real generated samples (ci-enroll vs ci-other seeds,
the same ones the CLI smoke test uses):

    Modality       old cosine (bug)   new distance-sim   default threshold
    fingerprint    0.9974             0.6189             0.80  (now rejected)
    video          0.9159             0.4393             0.75  (now rejected)
    voice          0.9762             0.6213             0.85  (now rejected)

Genuine self-matches stayed at 1.0000 in all three cases -- only impostor
scores moved. Normalized Euclidean distance was needed instead.

Communication / relationships
-----------------------------
Standard library: math.
Imported by:
- biometrics/features/fingerprint_features.py
- biometrics/features/video_features.py
- biometrics/features/voice_features.py
Covered by tests: no test file imports this module directly.

Settings / parameters
---------------------
No module-level constants, environment variables, or defaulted arguments:
behaviour is controlled entirely by the values callers pass in.

Edge cases
----------
Defines no error paths of its own: it raises nothing and catches nothing, so
any exception from the standard library or a dependency reaches the caller
unchanged.

Known limitations
-----------------
- BACKGROUND: all three modalities previously used plain cosine similarity,
  which only measures the ANGLE between two vectors, not how far apart their
  actual values are.
- Mean-centering (Pearson-correlation-style cosine) was tried first and barely
  helped (fingerprint only moved 0.9974 -> 0.9961): cosine is fundamentally an
  angle-only metric, and this feature space's impostor/genuine separation lives
  in magnitude of difference, not angle.
- No test module imports this file directly; it is exercised only through its
  callers' tests, so check changes manually.

Examples
--------
Call shapes only, not a runnable script: vector_a, vector_b stand for values
the caller supplies.

::

    from biometrics.features.similarity import distance_similarity
    distance_similarity(vector_a, vector_b)
"""

import math


def distance_similarity(vector_a: list, vector_b: list) -> float:
    """Similarity in (0.0, 1.0] based on Euclidean distance between two
    equal-length feature vectors, normalized by their own average
    magnitude and mapped through exponential decay so identical vectors
    score exactly 1.0 and similarity falls off smoothly and boundedly as
    the vectors diverge.

    Unlike cosine similarity, this is sensitive to how far apart the
    vectors' actual values are, not just the angle between them -- which
    is what lets it discriminate real impostors on magnitude-heavy
    feature spaces where cosine could not (see module docstring).

    The scale (half the vectors' average norm) makes the result
    self-relative to each pair's own magnitude, the same way cosine
    similarity is scale-invariant by construction, rather than comparing
    against one fixed, hardcoded distance constant that would only be
    correctly tuned for one particular vector magnitude.

    Callers are expected to have already validated that vector_a and
    vector_b are the same length; this function assumes it.
    """
    if not vector_a:
        return 0.0
    distance = sum((a - b) ** 2 for a, b in zip(vector_a, vector_b)) ** 0.5
    magnitude_a = sum(a * a for a in vector_a) ** 0.5
    magnitude_b = sum(b * b for b in vector_b) ** 0.5
    scale = (magnitude_a + magnitude_b) / 4.0  # i.e. 0.5 * average magnitude
    if scale == 0:
        # Both vectors are all-zero: identical-zero counts as a perfect
        # match rather than dividing by zero.
        return 1.0
    return math.exp(-distance / scale)




