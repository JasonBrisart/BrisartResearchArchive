"""
File: brisart_security_entropy.py

Purpose
-------
The only place in the Brisart Research Archive 97_Encryption project that
touches non-deterministic randomness. It asks the operating system for fresh
bytes through the standard-library ``secrets`` module, runs catastrophic-failure
health checks on every sample, and hands the result to the envelope, sealed
message, stream, archive, and key-generation layers.

Communication / relationships
-----------------------------
Imports ``os``, ``secrets``, ``threading`` (standard library only). Imported by
brisart_security_envelope.py (legacy v2 salt/nonce diversification),
brisart_security_drbg.py (``BrisartDRBG.from_system_entropy``),
brisart_security_aead.py, brisart_security_stream.py,
brisart_security_archive.py, and brisart_security_keys.py.

Settings / parameters
---------------------
HEALTH_SAMPLE_BYTES   32. Requests shorter than this are served from a
                      32-byte health-checked draw and truncated, so the
                      all-zero and repeat checks never misfire on short reads.
MAX_ENTROPY_REQUEST   1 MiB per call.
_PREVIOUS_SAMPLE      Last full health sample (process-local, lock protected).
_OWNER_PID            PID that owns _PREVIOUS_SAMPLE; reset after fork.

Edge cases
----------
* Lengths must be real ints (``True`` is rejected).
* An all-zero draw, a draw made of one repeated byte value, or a draw equal to
  the previous draw raises ``BrisartEntropyError``; the previous-sample memory
  is cleared on that failure so a retry is possible.
* After ``os.fork`` the child discards the parent's previous-sample memory
  instead of comparing against it.

Known limitations
-----------------
The checks detect a stuck or broken source, not a weak one. This module does
not estimate entropy and does not validate the operating system's generator.
A full machine snapshot that also rolls back OS randomness is out of reach for
any process-local code.

Examples
--------
>>> from brisart_security_entropy import system_entropy
>>> len(system_entropy(32))
32
"""
from __future__ import annotations

import os
import secrets
import threading

HEALTH_SAMPLE_BYTES = 32
MAX_ENTROPY_REQUEST = 1024 * 1024


class BrisartEntropyError(RuntimeError):
    """Raised when fresh operating-system entropy cannot be obtained safely."""


_LOCK = threading.Lock()
_PREVIOUS_SAMPLE: bytes | None = None
_OWNER_PID = os.getpid()


def system_entropy(length: int) -> bytes:
    """Return fresh operating-system entropy after basic health checks.

    The checks are catastrophic-failure detectors only. They are not an entropy
    estimate and do not validate the operating-system source.
    """
    global _PREVIOUS_SAMPLE, _OWNER_PID
    if type(length) is not int or length <= 0:
        raise BrisartEntropyError("entropy length must be a positive integer")
    if length > MAX_ENTROPY_REQUEST:
        raise BrisartEntropyError("entropy request exceeds the size limit")
    request = max(length, HEALTH_SAMPLE_BYTES)
    try:
        sample = secrets.token_bytes(request)
    except Exception as exc:
        raise BrisartEntropyError(
            "operating-system entropy request failed"
        ) from exc
    if not isinstance(sample, bytes) or len(sample) != request:
        raise BrisartEntropyError(
            "operating-system entropy returned an invalid result"
        )
    if not any(sample):
        raise BrisartEntropyError(
            "operating-system entropy returned an all-zero sample"
        )
    if sample.count(sample[0]) == len(sample):
        raise BrisartEntropyError(
            "operating-system entropy returned a constant sample"
        )
    with _LOCK:
        pid = os.getpid()
        if pid != _OWNER_PID:
            _OWNER_PID = pid
            _PREVIOUS_SAMPLE = None
        if _PREVIOUS_SAMPLE == sample:
            _PREVIOUS_SAMPLE = None
            raise BrisartEntropyError(
                "operating-system entropy repeated the previous sample"
            )
        _PREVIOUS_SAMPLE = sample
    return sample[:length]
