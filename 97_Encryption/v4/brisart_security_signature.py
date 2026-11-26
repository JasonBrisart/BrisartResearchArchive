"""
File: brisart_security_signature.py

Purpose
-------
Ed25519 digital signatures (RFC 8032, PureEdDSA) in pure Python, so that a tool
can prove who issued a file while the program that checks it holds only a
public key. This is the one public-key primitive in 97_Encryption.

It is the published, widely reviewed Ed25519 algorithm, not a BSR2 research
construction: the same keys and signatures interoperate with any other Ed25519
implementation, and nothing here depends on the BSR2 permutation. Only the
randomness for a new key comes from this project (brisart_security_entropy.py).

Communication / relationships
-----------------------------
Imports ``hashlib`` (SHA-512, standard library) and brisart_security_entropy.py
(``system_entropy``, the project's only source of randomness). Imports nothing
else from this project, so it can be used without the BSR2 modules.
Used by 98_Tooling/Entitle: entitle/encryption.py links it, and entitle/signing.py
is the only Entitle module that calls it (entitlements.py, revocation_list.py and
checkpoints.py sign and verify through signing.py). Also used by
tests/test_brisart_security_signature.py.

Settings / parameters
---------------------
ALGORITHM          "Ed25519"
SEED_BYTES         32  (the private key, called a seed in RFC 8032)
PUBLIC_KEY_BYTES   32
SIGNATURE_BYTES    64  (R | S, both little-endian as in RFC 8032)
generate_seed()           new private key from health-checked system entropy
public_key(seed)          the 32-byte public key for a seed
sign(seed, message)       the 64-byte signature (deterministic)
verify(public, message, signature)   True or False, never raises

Edge cases
----------
* verify() returns False, without raising, for a public key or signature of the
  wrong type or length, a public key or R that is not a canonical curve-point
  encoding (including y >= p), and an S that is not below the group order L
  (RFC 8032 section 5.1.7), so a valid signature has exactly one accepted form.
* verify() also refuses a public key of small order (the identity and the seven
  other points whose multiple by 8 is the identity). RFC 8032 allows them, but
  under such a key a signature for any message can be computed by anyone, so a
  mistaken or damaged key file would otherwise trust everybody. No key made by
  public_key() has small order, so valid keys are unaffected.
* sign() and public_key() raise BrisartSignatureError for a seed that is not
  exactly 32 bytes; generate_seed() raises it if the entropy health check fails.
* Signing is deterministic: the same seed and message give the same signature,
  so signing needs no random number and a weak generator cannot leak the key.
* The empty message is valid. verify() accepts bytes or bytearray.

Known limitations
-----------------
* Python integers are not constant-time, so sign() and public_key() can leak
  timing information about the seed to an observer on the same machine. Sign
  only on the owner's own machine. verify() handles no secret.
* Only PureEdDSA is provided (no Ed25519ctx, Ed25519ph or batch verification).
* Pure Python: about 20 ms per signature or verification on CPython 3.12. That
  suits licence files, revocation lists and checkpoints, not bulk signing.
* Only the standard algorithm is implemented; there is no key file, password
  protection or command-line interface here. Callers store the seed themselves
  (Entitle seals it with BSR2 under a passphrase).

Examples
--------
>>> from brisart_security_signature import generate_seed, public_key, sign, verify
>>> seed = generate_seed()
>>> public = public_key(seed)
>>> signature = sign(seed, b"message")
>>> verify(public, b"message", signature)
True
>>> verify(public, b"messagE", signature)
False
"""
import hashlib

from brisart_security_entropy import BrisartEntropyError, system_entropy

ALGORITHM = "Ed25519"
SEED_BYTES = 32
PUBLIC_KEY_BYTES = 32
SIGNATURE_BYTES = 64

_P = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)


class BrisartSignatureError(ValueError):
    """Raised when a seed passed to generate_seed(), sign() or public_key() is unusable."""


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


# Points are extended homogeneous coordinates (X, Y, Z, T) with x = X/Z, y = Y/Z, xy = T/Z.
def _add(p: tuple, q: tuple) -> tuple:
    a = (p[1] - p[0]) * (q[1] - q[0]) % _P
    b = (p[1] + p[0]) * (q[1] + q[0]) % _P
    c = 2 * p[3] * q[3] * _D % _P
    d = 2 * p[2] * q[2] % _P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _multiply(scalar: int, point: tuple) -> tuple:
    result = (0, 1, 1, 0)
    while scalar:
        if scalar & 1:
            result = _add(result, point)
        point = _add(point, point)
        scalar >>= 1
    return result


def _equal(p: tuple, q: tuple) -> bool:
    return (p[0] * q[2] - q[0] * p[2]) % _P == 0 and (p[1] * q[2] - q[1] * p[2]) % _P == 0


def _recover_x(y: int, sign: int) -> int | None:
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _SQRT_M1 % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


_GY = 4 * pow(5, _P - 2, _P) % _P
_GX = _recover_x(_GY, 0)
_G = (_GX, _GY, 1, _GX * _GY % _P)


def _is_small_order(point: tuple) -> bool:
    """True for the eight points of order 1, 2, 4 or 8, such as the identity (0, 1)."""
    return _equal(_multiply(8, point), (0, 1, 1, 0))


def _compress(point: tuple) -> bytes:
    z_inverse = pow(point[2], _P - 2, _P)
    x = point[0] * z_inverse % _P
    y = point[1] * z_inverse % _P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(data: bytes) -> tuple | None:
    if len(data) != 32:
        return None
    y = int.from_bytes(data, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % _P)


def _expand(seed: bytes) -> tuple[int, bytes]:
    if not isinstance(seed, (bytes, bytearray)) or len(seed) != SEED_BYTES:
        raise BrisartSignatureError(f"an Ed25519 private key must be exactly {SEED_BYTES} bytes")
    digest = _sha512(bytes(seed))
    scalar = int.from_bytes(digest[:32], "little")
    scalar &= (1 << 254) - 8
    scalar |= 1 << 254
    return scalar, digest[32:]


def generate_seed() -> bytes:
    """A new private key: 32 health-checked bytes from brisart_security_entropy."""
    try:
        return system_entropy(SEED_BYTES)
    except BrisartEntropyError as exc:
        raise BrisartSignatureError("fresh entropy failed while generating a signing key") from exc


def public_key(seed: bytes) -> bytes:
    scalar, _ = _expand(seed)
    return _compress(_multiply(scalar, _G))


def sign(seed: bytes, message: bytes) -> bytes:
    scalar, prefix = _expand(seed)
    message = bytes(message)
    public = _compress(_multiply(scalar, _G))
    r = int.from_bytes(_sha512(prefix + message), "little") % _L
    encoded_r = _compress(_multiply(r, _G))
    h = int.from_bytes(_sha512(encoded_r + public + message), "little") % _L
    s = (r + h * scalar) % _L
    return encoded_r + int.to_bytes(s, 32, "little")


def verify(public: bytes, message: bytes, signature: bytes) -> bool:
    """True only for a valid signature of message under public. Never raises for bad input."""
    try:
        if not isinstance(public, (bytes, bytearray)) or len(public) != PUBLIC_KEY_BYTES:
            return False
        if not isinstance(signature, (bytes, bytearray)) or len(signature) != SIGNATURE_BYTES:
            return False
        public, signature, message = bytes(public), bytes(signature), bytes(message)
        a = _decompress(public)
        r = _decompress(signature[:32])
        if a is None or r is None or _is_small_order(a):
            return False
        s = int.from_bytes(signature[32:], "little")
        if s >= _L:
            return False
        h = int.from_bytes(_sha512(signature[:32] + public + message), "little") % _L
        return _equal(_multiply(s, _G), _add(r, _multiply(h, a)))
    except (TypeError, ValueError):
        return False
