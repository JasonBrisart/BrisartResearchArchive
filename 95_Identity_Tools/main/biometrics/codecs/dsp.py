"""
File: biometrics/codecs/dsp.py

Purpose
-------
Signal-processing primitives shared by the voice feature extractor.

Public interface:
- class DspError(ValueError) -- Raised on invalid signal-processing parameters
  or input.
- frame_signal(samples, frame_size=DEFAULT_FRAME_SIZE,
  hop_size=DEFAULT_HOP_SIZE) -- Split a sample stream into overlapping
  fixed-size frames.
- apply_hamming_window(frame) -- Apply a Hamming window to reduce spectral
  leakage at frame edges.
- short_time_energy(frame) -- Mean squared amplitude of a frame -- a proxy for
  loudness.
- zero_crossing_rate(frame) -- Fraction of adjacent sample pairs that cross
  zero.
- discrete_cosine_transform(values, output_length) -- Naive DCT-II, truncated
  to the first ``output_length`` coefficients.
- band_energies(frame, band_count) -- Split a frame into contiguous bands and
  return each band's energy.
- normalize_vector(values) -- Scale a vector to unit maximum absolute value.

Design notes:

Implemented as plain loops over Python lists rather than with a numeric
library. Frame sizes used elsewhere in biometrics are small (on the order of a
few hundred samples), so the O(n) and O(n^2) costs here are not a practical
bottleneck, and keeping the implementation transparent matters more than
shaving milliseconds off it.

Communication / relationships
-----------------------------
Standard library: math.
Imported by:
- biometrics/features/voice_features.py
Covered by tests: biometrics/tests/test_codec_and_dsp_support.py.

Settings / parameters
---------------------
- DEFAULT_FRAME_SIZE = 512
- DEFAULT_HOP_SIZE = 256

Edge cases
----------
- frame_signal() raises DspError: "frame_size must be at least 1."
- frame_signal() raises DspError: "hop_size must be at least 1."
- discrete_cosine_transform() raises DspError: "output_length must be at least
  1."
- band_energies() raises DspError: "band_count must be at least 1."

Known limitations
-----------------
- No known limitations beyond the documented contract of its public interface.

Examples
--------
::

    from biometrics.codecs.dsp import (
        frame_signal,
        apply_hamming_window,
        short_time_energy,
    )
    result = frame_signal(samples)
    apply_hamming_window(frame)
    short_time_energy(frame)
"""

import math

DEFAULT_FRAME_SIZE = 512
DEFAULT_HOP_SIZE = 256


class DspError(ValueError):
    """Raised on invalid signal-processing parameters or input."""


def frame_signal(samples: list, frame_size: int = DEFAULT_FRAME_SIZE, hop_size: int = DEFAULT_HOP_SIZE) -> list:
    """Split a sample stream into overlapping fixed-size frames.

    The final partial frame, if any, is zero-padded rather than dropped, so a
    short recording still yields at least one frame instead of an empty
    feature set.
    """
    if frame_size < 1:
        raise DspError("frame_size must be at least 1.")
    if hop_size < 1:
        raise DspError("hop_size must be at least 1.")
    if not samples:
        return []
    frames = []
    position = 0
    while position < len(samples):
        chunk = samples[position:position + frame_size]
        if len(chunk) < frame_size:
            chunk = chunk + [0] * (frame_size - len(chunk))
        frames.append(chunk)
        position += hop_size
    return frames


def apply_hamming_window(frame: list) -> list:
    """Apply a Hamming window to reduce spectral leakage at frame edges."""
    length = len(frame)
    if length <= 1:
        return list(frame)
    return [
        sample * (0.54 - 0.46 * math.cos(2 * math.pi * index / (length - 1)))
        for index, sample in enumerate(frame)
    ]


def short_time_energy(frame: list) -> float:
    """Mean squared amplitude of a frame -- a proxy for loudness."""
    if not frame:
        return 0.0
    return sum(sample * sample for sample in frame) / len(frame)


def zero_crossing_rate(frame: list) -> float:
    """Fraction of adjacent sample pairs that cross zero.

    A cheap, well-established proxy for how "noisy" versus "tonal" a frame is;
    voiced speech has a markedly lower zero-crossing rate than unvoiced
    fricatives or background noise.
    """
    if len(frame) < 2:
        return 0.0
    crossings = 0
    for index in range(1, len(frame)):
        if (frame[index - 1] >= 0) != (frame[index] >= 0):
            crossings += 1
    return crossings / (len(frame) - 1)


def discrete_cosine_transform(values: list, output_length: int) -> list:
    """Naive DCT-II, truncated to the first ``output_length`` coefficients.

    Used to compress a frame's spectral-magnitude-like summary down to a small
    fixed-length vector, the same role an MFCC pipeline's DCT step plays,
    without requiring an FFT library. ``O(n * output_length)``, which is
    acceptable at the small frame sizes used here.
    """
    if output_length < 1:
        raise DspError("output_length must be at least 1.")
    length = len(values)
    if length == 0:
        return [0.0] * output_length
    coefficients = []
    for k in range(output_length):
        total = 0.0
        for n, value in enumerate(values):
            total += value * math.cos(math.pi / length * (n + 0.5) * k)
        coefficients.append(total)
    return coefficients


def band_energies(frame: list, band_count: int) -> list:
    """Split a frame into contiguous bands and return each band's energy.

    A coarse stand-in for a filterbank: instead of a true frequency-domain
    decomposition, the time-domain frame itself is partitioned and each
    segment's energy is measured. Combined with windowing and the DCT step,
    this gives a fixed-length, deterministic summary suitable for a template
    without any FFT dependency.
    """
    if band_count < 1:
        raise DspError("band_count must be at least 1.")
    if not frame:
        return [0.0] * band_count
    base, remainder = divmod(len(frame), band_count)
    energies = []
    cursor = 0
    for index in range(band_count):
        size = base + (1 if index < remainder else 0)
        segment = frame[cursor:cursor + size]
        energies.append(short_time_energy(segment))
        cursor += size
    return energies


def normalize_vector(values: list) -> list:
    """Scale a vector to unit maximum absolute value.

    An all-zero (silent) vector is returned unchanged rather than divided by
    zero.
    """
    if not values:
        return []
    peak = max(abs(value) for value in values)
    if peak == 0:
        return list(values)
    return [value / peak for value in values]




