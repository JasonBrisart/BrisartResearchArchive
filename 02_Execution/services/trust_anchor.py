"""
services/trust_anchor.py

The public key below is embedded directly in the application's own
source code -- it ships as part of the app itself and is NEVER fetched
from the website at update-check time.

If the website is ever compromised, an attacker can edit any page and
replace any hosted file -- but they cannot produce a signature that
verifies against the public key below, because that requires the
matching PRIVATE key, which lives offline, only on the Licensor's own
machine, and has never touched the website.

ROTATION: run `python signing/sign_release.py generate-keys --force`
completely offline, paste the new PUBLIC_KEY_DICT below, ship a new app
version, then re-sign all current releases with the new private key.
"""

from services import rsa_signing

# Replace with your own real generated public key before real use.
PUBLIC_KEY_DICT = {
    "e": "0x10001",
    "n": "0x0",  # PLACEHOLDER -- must be replaced with a real generated key
}


def get_public_key():
    return rsa_signing.public_key_from_dict(PUBLIC_KEY_DICT)