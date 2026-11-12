"""
File: entitle/signing.py

Purpose
-------
Own everything about issuer signatures: Ed25519 key pairs, the two key files (a public key that
  is safe to hand to anyone, and a signing key sealed under a passphrase), and the signed
  document format that signed entitlements, revocation lists and log checkpoints share. A
  program that checks a signed document holds only the public key, so it can verify but can
  never issue; that is the property shared-key (sealed) entitlements cannot give.

Communication / relationships
-----------------------------
Imports entitle/common.py (EntitleError, canonical_json, require_identifier, utc_now_iso,
  write_text_atomically) and entitle/encryption.py (signatures, the linked Ed25519 module;
  require, the linked BSR2, used to seal and open signing-key files and for its entropy source,
  which supplies the key-file salt). Imported by entitle/entitlements.py (signed entitlements),
  entitle/revocation_list.py, entitle/checkpoints.py, cli.py (keys commands) and gui/tabs.py (Keys
  tab). Covered by tests/test_signing.py.

Settings / parameters
---------------------
A key ID is the first 32 hex characters of SHA-256 over "Entitle Ed25519 key", a zero byte and
  the 32-byte public key. A public key file is JSON (format entitle.public-key.v1: algorithm,
  name, key_id, public_key in hex, created_at). A signing key file is JSON (format
  entitle.signing-key.v1) holding the same public fields plus the kdf used and the private seed
  sealed with BSR2 (BSR2-S64-SIV) under a key stretched from the passphrase with scrypt
  (N=2**15, r=8, p=1, 16-byte salt), or PBKDF2-HMAC-SHA256 (600,000 rounds) where this Python
  has no scrypt. MIN_PASSPHRASE_BYTES is 12. A signed document is armored text:

      -----BEGIN ENTITLE SIGNED <KIND>-----
      Algorithm: Ed25519
      Key-Id: <key id>
      Signature: <base64 signature>

      <base64 of the canonical JSON payload, 64 characters per line>
      -----END ENTITLE SIGNED <KIND>-----

  where KIND is ENTITLEMENT, REVOCATION LIST or CHECKPOINT. The signature covers
  "Entitle signed <kind> v1", a zero byte, and the payload bytes, so a signature made for one
  kind of document can never be presented as another.

Edge cases
----------
open_document raises SignatureRejected with a machine-readable reason: not_signed_document
  (wrong or damaged armor, or a different kind), unknown_signing_key (no trusted key has that
  key ID), signature_invalid, or payload_invalid (the signed bytes are not a JSON object). A
  payload over MAX_DOCUMENT_BYTES is refused before any signature check. Loading a public key
  file checks that its key ID matches its key, so a damaged file is named, not trusted.
  Loading a signing key checks the passphrase (BSR2 authentication) and that the opened seed
  produces the stored public key. Key files are written in one step and never overwrite an
  existing file unless asked; the signing key file is owner-only on POSIX.

Known limitations
-----------------
A passphrase is only as strong as it is long and unguessable; the KDF slows guessing, it does
  not prevent it. There is no key expiry or rotation record: to retire a key, stop trusting its
  public key file. Signing runs in pure Python (milliseconds) and is not constant-time, so sign
  on the issuer's own machine. The passphrase-sealed file depends on BSR2, which is experimental
  research cryptography; the signatures themselves are standard Ed25519.

Examples
--------
From the directory containing run.py:

    from tempfile import TemporaryDirectory
    from entitle.signing import generate_key_pair, load_signing_key, open_document, sign_document

    with TemporaryDirectory() as folder:
        public = generate_key_pair(name="Issuer", signing_key_path=f"{folder}/issuer.signing-key",
                                   public_key_path=f"{folder}/issuer.public-key",
                                   passphrase="correct horse battery staple")
        key = load_signing_key(f"{folder}/issuer.signing-key", "correct horse battery staple")
        text = sign_document("checkpoint", {"n": 1}, key)
        payload, signer = open_document(text, "checkpoint", [public])
        assert payload == {"n": 1} and signer.key_id == public.key_id
"""
import base64
import binascii
import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .common import EntitleError, canonical_json, require_identifier, utc_now_iso, write_text_atomically
from .encryption import require, signatures

PUBLIC_KEY_FORMAT = "entitle.public-key.v1"
SIGNING_KEY_FORMAT = "entitle.signing-key.v1"
ALGORITHM = "Ed25519"
MIN_PASSPHRASE_BYTES = 12
MAX_DOCUMENT_BYTES = 1024 * 1024
MAX_KEY_FILE_BYTES = 64 * 1024
KINDS = {"entitlement": "ENTITLEMENT", "revocation-list": "REVOCATION LIST", "checkpoint": "CHECKPOINT"}
_SCRYPT = {"name": "scrypt", "n": 2**15, "r": 8, "p": 1}
_PBKDF2 = {"name": "pbkdf2-hmac-sha256", "rounds": 600_000}


class SignatureRejected(EntitleError):
    """A signed document did not verify; .reason says why in one machine-readable word."""

    def __init__(self, reason, message=None):
        super().__init__(message or reason)
        self.reason = reason


@dataclass(frozen=True)
class PublicKey:
    name: str
    key_id: str
    raw: bytes = field(repr=False)

    def to_dict(self):
        return {"name": self.name, "key_id": self.key_id, "algorithm": ALGORITHM, "public_key": self.raw.hex()}


@dataclass(frozen=True)
class SigningKey:
    public: PublicKey
    seed: bytes = field(repr=False)

    @property
    def key_id(self):
        return self.public.key_id


def key_id_for(raw):
    return hashlib.sha256(b"Entitle Ed25519 key\x00" + bytes(raw)).hexdigest()[:32]


def _as_bytes(value):
    return value if isinstance(value, bytes) else str(value).encode("utf-8")


def _read_small(path, limit, what):
    path = Path(path)
    if path.stat().st_size > limit:
        raise ValueError(f"{path.name} is too large to be {what}.")
    try:
        return path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError(f"{path.name} is not {what} (it is not UTF-8 text).") from None


# Keys ---------------------------------------------------------------------------------------------

def _derive(passphrase, kdf, salt):
    secret = _as_bytes(passphrase)
    if kdf["name"] == "scrypt":
        return hashlib.scrypt(secret, salt=salt, n=kdf["n"], r=kdf["r"], p=kdf["p"], maxmem=128 * 1024 * 1024, dklen=64)
    if kdf["name"] == "pbkdf2-hmac-sha256":
        return hashlib.pbkdf2_hmac("sha256", secret, salt, kdf["rounds"], dklen=64)
    raise ValueError(f"unknown key derivation {kdf['name']!r}.")


def _seal_context(name, key_id):
    return json.dumps({"system": "Entitle", "purpose": "signing-key", "name": name, "key_id": key_id},
                      sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _check_passphrase(passphrase):
    if passphrase is None or len(_as_bytes(passphrase)) < MIN_PASSPHRASE_BYTES:
        raise ValueError(f"the passphrase must be at least {MIN_PASSPHRASE_BYTES} bytes long.")


def repository_containing(path):
    """The Git working tree that path would be written into, or None."""
    for folder in Path(path).resolve().parents:
        if (folder / ".git").exists():
            return folder
    return None


def generate_key_pair(
    *, name, signing_key_path, public_key_path, passphrase, overwrite=False, allow_in_repository=False
):
    """Create an issuer key pair and write both files. Returns the PublicKey."""
    require_identifier(name=name)
    repository = repository_containing(signing_key_path)
    if repository is not None and not allow_in_repository:
        raise ValueError(
            f"{signing_key_path} is inside the Git working tree {repository.name}; a signing key there is one "
            "'git add' away from being published. Keep it outside the repository (for example in a folder in "
            "your home directory or on removable media)."
        )
    _check_passphrase(passphrase)
    if Path(signing_key_path).resolve() == Path(public_key_path).resolve():
        raise ValueError("the signing key and the public key need two different files.")
    for path in (signing_key_path, public_key_path):
        if not overwrite and Path(path).exists():
            raise FileExistsError(f"{path} already exists. Choose another path, or overwrite it on purpose.")
    ed25519 = signatures()
    bsr2 = require()
    seed = ed25519.generate_seed()
    raw = ed25519.public_key(seed)
    public = PublicKey(name=name, key_id=key_id_for(raw), raw=raw)
    kdf = dict(_SCRYPT) if hasattr(hashlib, "scrypt") else dict(_PBKDF2)
    salt = bsr2.entropy.system_entropy(16)
    kdf["salt"] = salt.hex()
    sealed = bsr2.aead.seal(_derive(passphrase, kdf, salt), seed, _seal_context(name, public.key_id), padding="block")
    created = utc_now_iso()
    signing_file = {
        "format": SIGNING_KEY_FORMAT, **public.to_dict(), "created_at": created, "kdf": kdf,
        "sealed_seed": bsr2.aead.armor(sealed),
    }
    write_text_atomically(signing_key_path, json.dumps(signing_file, indent=2, ensure_ascii=False),
                          overwrite=overwrite, private=True)
    write_public_key(public, public_key_path, overwrite=overwrite, created_at=created)
    return public


def write_public_key(public, path, *, overwrite=False, created_at=None):
    document = {"format": PUBLIC_KEY_FORMAT, **public.to_dict(), "created_at": created_at or utc_now_iso()}
    write_text_atomically(path, json.dumps(document, indent=2, ensure_ascii=False), overwrite=overwrite)


def _public_from(document, path):
    name = Path(path).name
    if not isinstance(document, dict) or document.get("algorithm") != ALGORITHM:
        raise ValueError(f"{name} is not an Entitle Ed25519 key file.")
    try:
        raw = bytes.fromhex(document["public_key"])
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"{name} has no readable public key.") from None
    if len(raw) != 32 or document.get("key_id") != key_id_for(raw):
        raise ValueError(f"{name} is damaged: its key ID does not match its public key.")
    if not isinstance(document.get("name"), str):
        raise ValueError(f"{name} has no key name.")
    return PublicKey(name=document["name"], key_id=document["key_id"], raw=raw)


def _load_json(path, what):
    try:
        return json.loads(_read_small(path, MAX_KEY_FILE_BYTES, what))
    except json.JSONDecodeError:
        raise ValueError(f"{Path(path).name} is not {what}.") from None


def load_public_key(path):
    document = _load_json(path, "an Entitle public key file")
    if not isinstance(document, dict) or document.get("format") not in (PUBLIC_KEY_FORMAT, SIGNING_KEY_FORMAT):
        raise ValueError(f"{Path(path).name} is not an Entitle public key file.")
    return _public_from(document, path)


def load_public_keys(paths):
    """Load one or more public key files (a trust list). Duplicate keys are kept once."""
    keys = {}
    for path in [paths] if isinstance(paths, (str, os.PathLike)) else paths:
        key = load_public_key(path)
        keys.setdefault(key.key_id, key)
    return list(keys.values())


def load_signing_key(path, passphrase):
    document = _load_json(path, "an Entitle signing key file")
    name = Path(path).name
    if not isinstance(document, dict) or document.get("format") != SIGNING_KEY_FORMAT:
        raise ValueError(f"{name} is not an Entitle signing key file (a public key cannot sign).")
    public = _public_from(document, path)
    if passphrase is None:
        raise ValueError(f"{name} is protected by a passphrase; give it to use the key.")
    bsr2 = require()
    try:
        kdf = document["kdf"]
        key = _derive(passphrase, kdf, bytes.fromhex(kdf["salt"]))
        seed = bsr2.aead.unseal(key, bsr2.aead.dearmor(document["sealed_seed"]), _seal_context(public.name, public.key_id),
                                max_plaintext_bytes=64)
    except (KeyError, TypeError, ValueError, binascii.Error):
        seed = None
    except Exception:  # BSR2 reports authentication failures with its own exception types
        seed = None
    if seed is None or len(seed) != 32:
        raise EntitleError(f"the passphrase does not open {name} (or the file is damaged).")
    if signatures().public_key(seed) != public.raw:
        raise EntitleError(f"{name} is damaged: its private key does not match its public key.")
    return SigningKey(public=public, seed=seed)


# Signed documents ---------------------------------------------------------------------------------

def _armor_lines(kind):
    label = KINDS[kind]
    return f"-----BEGIN ENTITLE SIGNED {label}-----", f"-----END ENTITLE SIGNED {label}-----"


def _message(kind, payload_bytes):
    return f"Entitle signed {kind} v1".encode("ascii") + b"\x00" + payload_bytes


def is_signed_document(text, kind):
    return text.lstrip().startswith(_armor_lines(kind)[0])


def sign_document(kind, payload, signing_key):
    """Return the armored text of payload signed by signing_key."""
    payload_bytes = canonical_json(payload)
    if len(payload_bytes) > MAX_DOCUMENT_BYTES:
        raise ValueError(f"the {kind} is {len(payload_bytes):,} bytes, over the {MAX_DOCUMENT_BYTES:,} byte limit.")
    signature = signatures().sign(signing_key.seed, _message(kind, payload_bytes))
    encoded = base64.b64encode(payload_bytes).decode("ascii")
    begin, end = _armor_lines(kind)
    return "\n".join([
        begin,
        f"Algorithm: {ALGORITHM}",
        f"Key-Id: {signing_key.key_id}",
        f"Signature: {base64.b64encode(signature).decode('ascii')}",
        "",
        *[encoded[i:i + 64] for i in range(0, len(encoded), 64)],
        end,
    ]) + "\n"


def _parse(text, kind):
    begin, end = _armor_lines(kind)
    lines = [line.strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").strip().split("\n")]
    if len(lines) < 6 or lines[0] != begin or lines[-1] != end:
        raise SignatureRejected("not_signed_document", f"not a signed Entitle {kind}.")
    try:
        blank = lines.index("")
    except ValueError:
        raise SignatureRejected("not_signed_document", f"damaged signed {kind}: no blank line after the headers.") from None
    headers = {}
    for line in lines[1:blank]:
        key, separator, value = line.partition(":")
        if not separator or key.strip() in headers:
            raise SignatureRejected("not_signed_document", f"damaged signed {kind}: unreadable header {line!r}.")
        headers[key.strip()] = value.strip()
    body = "".join(lines[blank + 1:-1])
    if headers.get("Algorithm") != ALGORITHM or "Key-Id" not in headers or "Signature" not in headers:
        raise SignatureRejected("not_signed_document", f"damaged signed {kind}: missing or unknown headers.")
    if len(body) > (MAX_DOCUMENT_BYTES * 4) // 3 + 4:
        raise SignatureRejected("not_signed_document", f"the signed {kind} is too large.")
    try:
        payload_bytes = base64.b64decode(body, validate=True)
        signature = base64.b64decode(headers["Signature"], validate=True)
    except (binascii.Error, ValueError):
        raise SignatureRejected("not_signed_document", f"damaged signed {kind}: invalid base64.") from None
    return headers["Key-Id"], signature, payload_bytes


def _payload_object(payload_bytes, kind):
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        payload = None
    if not isinstance(payload, dict):
        raise SignatureRejected("payload_invalid", f"the signed {kind} does not hold a JSON object.")
    return payload


def open_document(text, kind, trusted_keys):
    """Verify text as a signed document of kind; return (payload, PublicKey that signed it)."""
    key_id, signature, payload_bytes = _parse(text, kind)
    trusted = {key.key_id: key for key in trusted_keys}
    if not trusted:
        raise ValueError("no public key was given to check the signature with.")
    key = trusted.get(key_id)
    if key is None:
        raise SignatureRejected("unknown_signing_key", f"signed by key {key_id}, which is not a trusted key.")
    if not signatures().verify(key.raw, _message(kind, payload_bytes), signature):
        raise SignatureRejected("signature_invalid", f"the signature on this {kind} is not valid.")
    return _payload_object(payload_bytes, kind), key


def peek_document(text, kind):
    """Return (payload, key_id) WITHOUT checking the signature. For display only; never trust it."""
    key_id, _, payload_bytes = _parse(text, kind)
    return _payload_object(payload_bytes, kind), key_id
