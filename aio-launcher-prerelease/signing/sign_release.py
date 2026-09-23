"""
signing/sign_release.py

OFFLINE, LICENSOR-ONLY tool. Run only on your own trusted machine.
Generates the signing key and produces the signed registry entry for
THIS app (brisart_research_archive), in the same combined-page format
used by every other Brisart tool.

    python signing/sign_release.py generate-keys
    python signing/sign_release.py sign --file BrisartResearchArchive-0.8.0.zip --version 0.8.0 --url "https://..."
"""

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import rsa_signing

KEYS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "signing", "keys")
PRIVATE_KEY_PATH = os.path.join(KEYS_DIR, "private_key.json")
APP_ID = "brisart_research_archive"


def cmd_generate_keys(args):
    os.makedirs(KEYS_DIR, exist_ok=True)
    if os.path.exists(PRIVATE_KEY_PATH) and not args.force:
        print("Private key already exists. Use --force to overwrite "
              "(this invalidates trust in all previously signed releases).")
        sys.exit(1)
    print(f"Generating {args.bits}-bit RSA keypair...")
    public_key, private_key = rsa_signing.generate_keypair(bits=args.bits)
    with open(PRIVATE_KEY_PATH, "w") as f:
        json.dump(rsa_signing.private_key_to_dict(private_key), f, indent=2)
    pub_dict = rsa_signing.public_key_to_dict(public_key)
    print(f"\nPrivate key written to: {PRIVATE_KEY_PATH}")
    print("KEEP THIS FILE OFFLINE. NEVER commit or upload it.\n")
    print("Paste this into services/trust_anchor.py, replacing PUBLIC_KEY_DICT:\n")
    print("PUBLIC_KEY_DICT = {")
    print(f'    "e": "{pub_dict["e"]}",')
    print(f'    "n": "{pub_dict["n"]}",')
    print("}")


def _sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def cmd_sign(args):
    if not os.path.exists(PRIVATE_KEY_PATH):
        print("No private key found. Run 'generate-keys' first.")
        sys.exit(1)
    with open(PRIVATE_KEY_PATH) as f:
        private_key = rsa_signing.private_key_from_dict(json.load(f))
    file_hash = _sha256_of_file(args.file)
    signature = rsa_signing.sign(bytes.fromhex(file_hash), private_key)
    entry = {
        "version": args.version,
        "download_url": args.url,
        "sha256": file_hash,
        "signature": signature.hex(),
    }
    print(f"Signed: {args.file}\n")
    print(f'Paste this as the "{APP_ID}" entry in the registry page:\n')
    print(f'"{APP_ID}": {json.dumps(entry, indent=2)}')


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p_gen = sub.add_parser("generate-keys")
    p_gen.add_argument("--bits", type=int, default=2048)
    p_gen.add_argument("--force", action="store_true")
    p_gen.set_defaults(func=cmd_generate_keys)
    p_sign = sub.add_parser("sign")
    p_sign.add_argument("--file", required=True)
    p_sign.add_argument("--version", required=True)
    p_sign.add_argument("--url", required=True)
    p_sign.set_defaults(func=cmd_sign)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()