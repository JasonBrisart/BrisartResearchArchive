"""
services/rsa_signing.py

Pure-Python RSA key generation and RSASSA-PKCS1-v1_5 signing/verification
(SHA-256). Standard library only. No pip installs.
"""

import hashlib
import secrets

_SMALL_PRIMES = [
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67,
    71, 73, 79, 83, 89, 97, 101, 103, 107, 109, 113, 127, 131, 137, 139,
    149, 151, 157, 163, 167, 173, 179, 181, 191, 193, 197, 199, 211, 223,
    227, 229, 233, 239, 241, 251,
]


def _is_probable_prime(n: int, rounds: int = 40) -> bool:
    if n < 2:
        return False
    for p in _SMALL_PRIMES:
        if n == p:
            return True
        if n % p == 0:
            return False
    d = n - 1
    r = 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(rounds):
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def generate_prime(bits: int) -> int:
    if bits < 8:
        raise ValueError("bits must be >= 8")
    while True:
        candidate = secrets.randbits(bits)
        candidate |= (1 << (bits - 1)) | 1
        if _is_probable_prime(candidate):
            return candidate


def _egcd(a: int, b: int):
    if b == 0:
        return (a, 1, 0)
    g, x1, y1 = _egcd(b, a % b)
    return (g, y1, x1 - (a // b) * y1)


def _modinv(a: int, m: int) -> int:
    g, x, _ = _egcd(a % m, m)
    if g != 1:
        raise ValueError("modular inverse does not exist")
    return x % m


def generate_keypair(bits: int = 2048):
    e = 65537
    while True:
        p = generate_prime(bits // 2)
        q = generate_prime(bits // 2)
        if p == q:
            continue
        n = p * q
        phi = (p - 1) * (q - 1)
        if _egcd(e, phi)[0] != 1:
            continue
        d = _modinv(e, phi)
        if n.bit_length() >= bits - 1:
            return (e, n), (d, n)


_SHA256_DIGEST_INFO_PREFIX = bytes.fromhex(
    "3031300d060960864801650304020105000420"
)


def _emsa_pkcs1_v15_encode(message: bytes, em_len: int) -> bytes:
    digest = hashlib.sha256(message).digest()
    t = _SHA256_DIGEST_INFO_PREFIX + digest
    t_len = len(t)
    if em_len < t_len + 11:
        raise ValueError("intended encoded message length too short")
    ps_len = em_len - t_len - 3
    ps = b"\xff" * ps_len
    return b"\x00\x01" + ps + b"\x00" + t


def sign(message: bytes, private_key) -> bytes:
    d, n = private_key
    k = (n.bit_length() + 7) // 8
    em = _emsa_pkcs1_v15_encode(message, k)
    m_int = int.from_bytes(em, "big")
    if m_int >= n:
        raise ValueError("message representative out of range")
    s_int = pow(m_int, d, n)
    return s_int.to_bytes(k, "big")


def verify(message: bytes, signature: bytes, public_key) -> bool:
    e, n = public_key
    k = (n.bit_length() + 7) // 8
    if len(signature) != k:
        return False
    s_int = int.from_bytes(signature, "big")
    if s_int >= n:
        return False
    m_int = pow(s_int, e, n)
    em = m_int.to_bytes(k, "big")
    try:
        expected = _emsa_pkcs1_v15_encode(message, k)
    except ValueError:
        return False
    return secrets.compare_digest(em, expected)


def public_key_to_dict(public_key) -> dict:
    e, n = public_key
    return {"e": hex(e), "n": hex(n)}


def public_key_from_dict(d: dict):
    return (int(d["e"], 16), int(d["n"], 16))


def private_key_to_dict(private_key) -> dict:
    d_, n = private_key
    return {"d": hex(d_), "n": hex(n)}


def private_key_from_dict(d: dict):
    return (int(d["d"], 16), int(d["n"], 16))