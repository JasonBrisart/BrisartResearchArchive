"""
File: services/trust_anchor.py

Purpose:
Embed the updater's public verification key directly in the application
and report whether a real key has been configured. The key is never
fetched from the website, so a compromised website cannot forge a
trusted release.

Communication / relationships:
- services/updater/download.py calls get_public_key() to verify release
  signatures.
- services/updater/orchestration.py calls is_configured() before any
  registry contact.
- signing/sign_release.py prints the PUBLIC_KEY_DICT to paste here.

Settings / parameters:
- PUBLIC_KEY_DICT: hex strings "e" and "n".
- MIN_MODULUS_BITS (2047): the shortest modulus treated as a real key.

Edge cases:
- The shipped placeholder ("n": "0x0") makes is_configured() return
  False; the updater then returns status "trust_anchor_unconfigured"
  without touching the network, instead of reporting every release as
  forged.
- A malformed dictionary also makes is_configured() return False.

Known limitations:
- Rotating the key requires shipping a new build, and releases signed
  with the old key then fail verification.
- The private key must stay offline; only the public half belongs here.

Examples:
- is_configured()
- public_key = get_public_key()
"""

from services.rsa_signing import public_key_from_dict

# Replace with the PUBLIC key printed by
# "python signing/sign_release.py generate-keys". The value below is a
# placeholder; is_configured() reports False until it is replaced, and the
# updater refuses to run in that state.
PUBLIC_KEY_DICT = {
    "e": "0x10001",
    "n": "0x0",
}

# signing/sign_release.py generates 2048-bit keys by default and accepts a
# modulus of bits - 1, so anything shorter than this is treated as unset.
MIN_MODULUS_BITS = 2047


def get_public_key():
    return public_key_from_dict(PUBLIC_KEY_DICT)


def is_configured() -> bool:
    try:
        exponent, modulus = get_public_key()
    except (KeyError, TypeError, ValueError):
        return False
    return exponent > 1 and modulus.bit_length() >= MIN_MODULUS_BITS


__all__ = ["PUBLIC_KEY_DICT", "MIN_MODULUS_BITS", "get_public_key", "is_configured"]
