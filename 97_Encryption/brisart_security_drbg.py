"""
File: brisart_security_drbg.py

Purpose
-------
BrisartDRBG, the custom deterministic random-bit generator. It expands seed
material with the legacy rate-32 sponge under ``BSR2/drbg-v2/*`` domains and
enforces lifecycle limits (request size, bytes and requests before reseed),
a continuous repeated-block health check, destruction, and reseeding. Output for
a given seed, personalization, and call sequence is frozen by the DRBG
known-answer vector.

Communication / relationships
-----------------------------
Imports ``frame`` and ``sponge_hash`` from brisart_security_primitives.py and
``system_entropy`` from brisart_security_entropy.py (only for
``from_system_entropy``). Consumed as the caller-supplied ``rng`` by
brisart_security_envelope.py, brisart_security_aead.py,
brisart_security_stream.py, and brisart_security_archive.py.

Settings / parameters
---------------------
MINIMUM_SEED_BYTES            64
MINIMUM_PERSONALIZATION_BYTES 16
MAX_PERSONALIZATION_BYTES     4096
MAX_ADDITIONAL_INPUT_BYTES    65,536 per request
MAX_REQUEST_BYTES             1 MiB
MAX_BYTES_BEFORE_RESEED       16 MiB
RESEED_INTERVAL               100,000 requests

Edge cases
----------
* Fork safety: the generator records its owner PID. If ``generate`` runs in a
  different process (``os.fork`` child), it destroys its state and raises until
  it is reseeded, so parent and child never emit the same stream.
* Cloning refusal: ``copy.copy``, ``copy.deepcopy`` and ``pickle`` raise
  ``TypeError``. Duplicating DRBG state is exactly the restart/reuse failure
  that Alpha 3 documented.
* A valid ``reseed`` reactivates a destroyed generator (unchanged behaviour).
* Lengths must be real ints; ``True`` is rejected.

Known limitations
-----------------
The generator cannot create entropy; its output is only as unpredictable as its
seed. It has not been analysed against state-compromise extension attacks.

Examples
--------
>>> from brisart_security_drbg import BrisartDRBG
>>> rng = BrisartDRBG.from_system_entropy(b"example personalization")
>>> len(rng.generate(32, b"request"))
32
"""
import os

from brisart_security_primitives import frame, sponge_hash

MINIMUM_SEED_BYTES = 64
MINIMUM_PERSONALIZATION_BYTES = 16
MAX_PERSONALIZATION_BYTES = 4096
MAX_ADDITIONAL_INPUT_BYTES = 64 * 1024
MAX_REQUEST_BYTES = 1024 * 1024
MAX_BYTES_BEFORE_RESEED = 16 * 1024 * 1024
RESEED_INTERVAL = 100_000


class BrisartDRBGError(ValueError):
    pass


class BrisartDRBG:
    """Fully custom deterministic research generator.

    This generator expands caller-provided seed material. It cannot create
    entropy. Its security cannot exceed the unpredictability of the seed.
    """

    def __init__(self, seed: bytes, personalization: bytes):
        self._require_seed(seed, "seed")
        if not isinstance(personalization, bytes):
            raise BrisartDRBGError("personalization must be bytes")
        if len(personalization) < MINIMUM_PERSONALIZATION_BYTES:
            raise BrisartDRBGError(
                "personalization must contain at least "
                f"{MINIMUM_PERSONALIZATION_BYTES} bytes"
            )
        if len(personalization) > MAX_PERSONALIZATION_BYTES:
            raise BrisartDRBGError("personalization exceeds the size limit")
        initial = sponge_hash(
            frame(seed) + frame(personalization),
            128,
            b"BSR2/drbg-v2/instantiate",
        )
        self._state = bytearray(initial)
        self._counter = 0
        self._requests = 0
        self._generated_bytes = 0
        self._previous_block = None
        self._destroyed = False
        self._owner_pid = os.getpid()

    @classmethod
    def from_system_entropy(cls, personalization: bytes) -> "BrisartDRBG":
        """Instantiate from 64 fresh operating-system bytes."""
        from brisart_security_entropy import system_entropy

        return cls(system_entropy(MINIMUM_SEED_BYTES), personalization)

    def __repr__(self) -> str:
        status = "destroyed" if self._destroyed else "active"
        return f"<BrisartDRBG {status} requests={self._requests}>"

    def __copy__(self):
        raise TypeError("BrisartDRBG state cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("BrisartDRBG state cannot be copied")

    def __reduce__(self):
        raise TypeError("BrisartDRBG state cannot be serialized")

    @staticmethod
    def _require_seed(seed: bytes, name: str) -> None:
        if not isinstance(seed, bytes):
            raise BrisartDRBGError(f"{name} must be bytes")
        if len(seed) < MINIMUM_SEED_BYTES:
            raise BrisartDRBGError(
                f"{name} must contain at least {MINIMUM_SEED_BYTES} bytes"
            )

    @staticmethod
    def _require_additional(additional_input: bytes, message: str) -> None:
        if not isinstance(additional_input, bytes) or not additional_input:
            raise BrisartDRBGError(message)
        if len(additional_input) > MAX_ADDITIONAL_INPUT_BYTES:
            raise BrisartDRBGError("additional input exceeds the size limit")

    def _require_active(self) -> None:
        if self._destroyed:
            raise BrisartDRBGError("generator state has been destroyed")
        if os.getpid() != self._owner_pid:
            self.destroy()
            raise BrisartDRBGError(
                "process fork detected; generator must be reseeded"
            )
        if self._requests >= RESEED_INTERVAL:
            raise BrisartDRBGError("generator reached its reseed interval")
        if self._generated_bytes >= MAX_BYTES_BEFORE_RESEED:
            raise BrisartDRBGError("generator reached its byte limit")

    def _preupdate(self, additional_input: bytes) -> None:
        self._state[:] = sponge_hash(
            frame(bytes(self._state))
            + frame(additional_input)
            + self._counter.to_bytes(16, "big"),
            128,
            b"BSR2/drbg-v2/preupdate",
        )

    def _next_block(self) -> bytes:
        counter = self._counter.to_bytes(16, "big")
        block = sponge_hash(
            frame(bytes(self._state)) + counter,
            64,
            b"BSR2/drbg-v2/output",
        )
        if self._previous_block is not None and block == self._previous_block:
            self.destroy()
            raise BrisartDRBGError(
                "continuous health check detected a repeated block"
            )
        next_state = sponge_hash(
            frame(bytes(self._state))
            + frame(block)
            + counter,
            128,
            b"BSR2/drbg-v2/postupdate",
        )
        self._state[:] = next_state
        self._previous_block = block
        self._counter += 1
        return block

    def generate(self, length: int, additional_input: bytes) -> bytes:
        self._require_active()
        if type(length) is not int or length <= 0:
            raise BrisartDRBGError("length must be a positive integer")
        if length > MAX_REQUEST_BYTES:
            raise BrisartDRBGError("request exceeds the size limit")
        self._require_additional(
            additional_input,
            "non-empty additional input is required for each request",
        )
        if self._generated_bytes + length > MAX_BYTES_BEFORE_RESEED:
            raise BrisartDRBGError("request would exceed the reseed byte limit")
        self._preupdate(additional_input)
        output = bytearray()
        while len(output) < length:
            output.extend(self._next_block())
        self._requests += 1
        self._generated_bytes += length
        return bytes(output[:length])

    def reseed(self, seed: bytes, additional_input: bytes) -> None:
        self._require_seed(seed, "reseed material")
        self._require_additional(
            additional_input,
            "non-empty reseed additional input is required",
        )
        self._state[:] = sponge_hash(
            frame(bytes(self._state))
            + frame(seed)
            + frame(additional_input),
            128,
            b"BSR2/drbg-v2/reseed",
        )
        self._counter = 0
        self._requests = 0
        self._generated_bytes = 0
        self._previous_block = None
        self._destroyed = False
        self._owner_pid = os.getpid()

    def destroy(self) -> None:
        for index in range(len(self._state)):
            self._state[index] = 0
        self._counter = 0
        self._requests = RESEED_INTERVAL
        self._generated_bytes = MAX_BYTES_BEFORE_RESEED
        self._previous_block = None
        self._destroyed = True
