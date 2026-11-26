"""
File: biometrics/codecs/dsp.py

Purpose
-------
Signal-processing primitives for the voice feature extractor: windowing, frame
energy, the discrete cosine transform, a fast Fourier transform, the mel
filterbank, and pitch estimation. Everything is implemented with plain Python
lists and the standard library so that biometric extraction keeps zero
third-party dependencies.

Public interface:
- class DspError(ValueError) -- Raised on invalid signal-processing parameters
  or input.
- apply_hamming_window(frame) -- Apply a Hamming window to reduce spectral
  leakage at frame edges.
- short_time_energy(frame) -- Mean squared amplitude of a frame -- a proxy for
  loudness.
- discrete_cosine_transform(values, output_length) -- Naive (unnormalised)
  DCT-II, truncated to the first ``output_length`` coefficients.
- next_power_of_two(value) -- Smallest power of two that is at least ``value``.
- fft(real_values, imag_values=None) -- Iterative radix-2 FFT returning
  ``(real, imag)``; the length must be a power of two.
- power_spectrum(frame, fft_size) -- One-sided power spectrum of a real frame,
  zero-padded or truncated to ``fft_size``.
- hz_to_mel(frequency) / mel_to_hz(mel) -- HTK mel scale conversions.
- mel_filterbank(filter_count, fft_size, sample_rate, low_hz, high_hz) --
  Triangular mel filters stored sparsely as ``(first_bin, weights)`` pairs.
- apply_filterbank(spectrum, bank) -- Filterbank energies of a power spectrum.
- estimate_pitch(frame, sample_rate, low_hz=70.0, high_hz=400.0,
  voicing_threshold=0.35) -- Fundamental frequency of a frame in Hz, or 0.0 when
  the frame is unvoiced.

Design notes:

Implemented as plain loops over Python lists rather than with a numeric
library. The FFT is a standard iterative radix-2 transform, O(n log n), which
makes frame sizes of a few hundred samples cheap (about a millisecond for a
256-point frame). It replaces the time-segment "band energies" this module used
to provide: splitting a frame into consecutive time segments says nothing about
frequency content, so those values could not tell speakers apart.

Pitch is found from the autocorrelation of a frame, computed through the FFT
(the Wiener-Khinchin relation): the strongest lag within the plausible speech
range gives the period, and a frame whose normalised peak is below the voicing
threshold is reported unvoiced.

Communication / relationships
-----------------------------
Standard library: math.
Imported by:
- biometrics/features/voice_features.py
Covered by tests: biometrics/tests/test_codec_and_dsp_support.py (windowing,
energy and the DCT) and biometrics/tests/test_voice_features.py (FFT, power
spectrum, filterbank and pitch).

Settings / parameters
---------------------
- apply_filterbank() and mel_filterbank() take their sizes from the caller;
  voice_features.py uses 24 filters between 100 Hz and 95% of the Nyquist
  frequency.
- estimate_pitch() searches 70 to 400 Hz by default and requires a normalised
  autocorrelation peak of 0.35 to call a frame voiced.

Edge cases
----------
- discrete_cosine_transform() raises DspError: "output_length must be at least
  1."; an empty input returns zeros.
- next_power_of_two() raises DspError: "value must be at least 1."
- fft() raises DspError: "fft length must be a power of two." and "real and
  imaginary parts must be the same length."
- mel_filterbank() raises DspError: "filter_count must be at least 1." and
  "filterbank frequency range is invalid."
- estimate_pitch() returns 0.0 for a silent frame, a frame too short to hold a
  period in range, and a frame without a clear periodic peak (noise).

Known limitations
-----------------
- Pure-Python speed: a transform of a few thousand points is fine, a long
  recording analysed frame by frame takes a noticeable fraction of a second.
- estimate_pitch() has integer-lag resolution (at 8 kHz, about 1.5 Hz at
  100 Hz and 6 Hz at 200 Hz) and can report an octave error on very noisy
  frames.
- The Hamming window and mel filterbank follow the common textbook
  definitions; they are not tuned for any particular microphone.

Examples
--------
Call shapes only, not a runnable script: samples stands for values the caller
supplies.

::

    from biometrics.codecs import dsp
    spectrum = dsp.power_spectrum(dsp.apply_hamming_window(frame), 256)
    bank = dsp.mel_filterbank(24, 256, 8000, 100.0, 3800.0)
    energies = dsp.apply_filterbank(spectrum, bank)
    pitch = dsp.estimate_pitch(frame, 8000)
"""

import math


class DspError(ValueError):
    """Raised on invalid signal-processing parameters or input."""


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




def next_power_of_two(value: int) -> int:
    """Smallest power of two that is >= ``value`` (and at least 1)."""
    if value < 1:
        raise DspError("value must be at least 1.")
    return 1 << (int(value) - 1).bit_length()


def fft(real_values: list, imag_values: list = None) -> tuple:
    """In-place-style iterative radix-2 FFT; returns ``(real, imag)`` lists.

    The input length must be a power of two. Pure standard-library so the
    biometric extractors keep zero third-party dependencies. ``O(n log n)``.
    """
    size = len(real_values)
    if size < 1 or size & (size - 1):
        raise DspError("fft length must be a power of two.")
    real = [float(value) for value in real_values]
    imag = [0.0] * size if imag_values is None else [float(value) for value in imag_values]
    if len(imag) != size:
        raise DspError("real and imaginary parts must be the same length.")
    # Bit-reversal permutation.
    target = 0
    for index in range(1, size):
        bit = size >> 1
        while target & bit:
            target ^= bit
            bit >>= 1
        target |= bit
        if index < target:
            real[index], real[target] = real[target], real[index]
            imag[index], imag[target] = imag[target], imag[index]
    length = 2
    while length <= size:
        angle = -2.0 * math.pi / length
        step_real, step_imag = math.cos(angle), math.sin(angle)
        half = length >> 1
        for start in range(0, size, length):
            w_real, w_imag = 1.0, 0.0
            for offset in range(half):
                low = start + offset
                high = low + half
                t_real = real[high] * w_real - imag[high] * w_imag
                t_imag = real[high] * w_imag + imag[high] * w_real
                real[high] = real[low] - t_real
                imag[high] = imag[low] - t_imag
                real[low] += t_real
                imag[low] += t_imag
                w_real, w_imag = (w_real * step_real - w_imag * step_imag,
                                  w_real * step_imag + w_imag * step_real)
        length <<= 1
    return real, imag


def power_spectrum(frame: list, fft_size: int) -> list:
    """One-sided power spectrum (``fft_size // 2 + 1`` bins) of a real frame.

    The frame is zero-padded (or truncated) to ``fft_size``.
    """
    padded = list(frame[:fft_size]) + [0.0] * max(0, fft_size - len(frame))
    real, imag = fft(padded)
    return [real[k] * real[k] + imag[k] * imag[k] for k in range(fft_size // 2 + 1)]


def hz_to_mel(frequency: float) -> float:
    """HTK mel scale."""
    return 2595.0 * math.log10(1.0 + frequency / 700.0)


def mel_to_hz(mel: float) -> float:
    """Inverse of :func:`hz_to_mel`."""
    return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)


def mel_filterbank(filter_count: int, fft_size: int, sample_rate: int,
                   low_hz: float, high_hz: float) -> list:
    """Triangular mel filterbank as a list of ``(first_bin, weights)`` pairs.

    Each filter is stored sparsely so applying the bank costs only the
    non-zero weights.
    """
    if filter_count < 1:
        raise DspError("filter_count must be at least 1.")
    nyquist = sample_rate / 2.0
    high_hz = min(high_hz, nyquist)
    if not 0 <= low_hz < high_hz:
        raise DspError("filterbank frequency range is invalid.")
    mel_low, mel_high = hz_to_mel(low_hz), hz_to_mel(high_hz)
    points = [mel_to_hz(mel_low + (mel_high - mel_low) * i / (filter_count + 1))
              for i in range(filter_count + 2)]
    bin_hz = sample_rate / fft_size
    bank = []
    for index in range(1, filter_count + 1):
        left, centre, right = points[index - 1], points[index], points[index + 1]
        first = max(0, int(left / bin_hz))
        last = min(fft_size // 2, int(right / bin_hz) + 1)
        weights = []
        for bin_index in range(first, last + 1):
            frequency = bin_index * bin_hz
            if left < frequency <= centre:
                weights.append((frequency - left) / (centre - left))
            elif centre < frequency < right:
                weights.append((right - frequency) / (right - centre))
            else:
                weights.append(0.0)
        bank.append((first, weights))
    return bank


def apply_filterbank(spectrum: list, bank: list) -> list:
    """Filterbank energies for a power spectrum."""
    energies = []
    for first, weights in bank:
        total = 0.0
        for offset, weight in enumerate(weights):
            if weight and first + offset < len(spectrum):
                total += weight * spectrum[first + offset]
        energies.append(total)
    return energies


def estimate_pitch(frame: list, sample_rate: int, low_hz: float = 70.0,
                   high_hz: float = 400.0, voicing_threshold: float = 0.35) -> float:
    """Fundamental frequency of a frame in Hz, or ``0.0`` when unvoiced.

    Uses the FFT-based autocorrelation (Wiener-Khinchin) and picks the
    strongest lag in the plausible speech range. A frame is voiced only when
    the normalised autocorrelation peak exceeds ``voicing_threshold``.
    """
    size = next_power_of_two(2 * len(frame))
    spectrum = power_spectrum(frame, size)
    full = spectrum + spectrum[-2:0:-1]
    real, _ = fft(full)
    if real[0] <= 0:
        return 0.0
    min_lag = max(2, int(sample_rate / high_hz))
    max_lag = min(len(frame) - 1, int(sample_rate / low_hz))
    if max_lag <= min_lag:
        return 0.0
    best_lag, best_value = 0, 0.0
    for lag in range(min_lag, max_lag + 1):
        value = real[lag] / real[0]
        if value > best_value:
            best_lag, best_value = lag, value
    if best_value < voicing_threshold or best_lag == 0:
        return 0.0
    return sample_rate / best_lag
