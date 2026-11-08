"""
File: crypto/tests/legacy_fixtures.py

Purpose
-------
Test support for the encryption migration: a real keyring in the previous
(v1) format, and helpers that write records in the previous encryption, so
the migration tests can build legacy vaults, biometrics stores, and packages
without the pre-migration code. Not a test module itself (no ``test_`` prefix),
so tests/run_tests.py does not collect it.

Public interface:
- LEGACY_KEYRING_STATE, LEGACY_PASSPHRASE, LEGACY_RECOVERY_CODE,
  LEGACY_MASTER_KEY -- a v1 keyring and the secrets that open it.
- seal_legacy_bytes(master_key, plaintext, context) /
  seal_legacy_json(master_key, payload, context) -- a legacy v2 envelope, laid
  out exactly as Identity Tools sealed them before the encryption migration (8-byte length
  prefix, zero padding to 256 bytes, BSR2-ARX-SPONGE-ETM).
- legacy_bind_factor(master_key, factor_name, value) -- a legacy
  ``bsr2$keyed_mac$`` binding.
- legacy_keyring_state(passphrase, memory_blocks=64) -- ``(state,
  master_key)`` for a current keyring whose check value is in the legacy form,
  so it needs migration without any slow legacy derivation; see Design notes.

Design notes:

LEGACY_KEYRING_STATE was produced by Keyring.create() with the v1 keyring
code, which runs the legacy iterated KDF at its 10,000-iteration floor, so
unlocking it takes about a minute and only slow tests use it. Fast tests get a
current keyring whose master_key_check is rewritten to the legacy keyed_mac
form with legacy_keyring_state(): Keyring.needs_migration is then True, but
migrate() needs no legacy KDF derivation.

The legacy writers call Brisart Encryption's legacy modules directly, the same
constructions the pre-migration code used; crypto/tests/test_encryption_link.py
checks that payloads sealed by 1.9.2 itself open and migrate.

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.encryption (crypto/encryption.py)
- crypto.keyring (crypto/keyring.py)
- crypto.rng (crypto/rng.py)
Standard library: json.
Imported by:
- biometrics/tests/test_encryption_migration.py
- crypto/tests/test_keyring.py
- packages/tests/test_package_migration.py
- vault/tests/test_vault_migration.py

Settings / parameters
---------------------
- _LEGACY_PADDING_BYTES = 256, _LEGACY_LENGTH_PREFIX_BYTES = 8

Edge cases
----------
None of its own; errors from Brisart Encryption propagate.

Known limitations
-----------------
- legacy_keyring_state() exercises the check-value path of
  Keyring.migrate(), not legacy wrapper re-derivation; LEGACY_KEYRING_STATE
  covers that in the slow tests.

Examples
--------
::

    from crypto.tests.legacy_fixtures import seal_legacy_json
    envelope = seal_legacy_json(master_key, {"a": 1}, context)
"""

import json

from crypto import encryption
from crypto.keyring import Keyring
from crypto.rng import new_generator

_LEGACY_PADDING_BYTES = 256
_LEGACY_LENGTH_PREFIX_BYTES = 8

LEGACY_PASSPHRASE = "legacy passphrase"
LEGACY_RECOVERY_CODE = "01234-56789-ABCDE-FGHJK-MNPQR-STVWX-YZ012-34567"
LEGACY_MASTER_KEY = bytes.fromhex(
    "6886722663586db403b3b50533a4c50de9c63e9f254d76e53d3cdf0d5d31e652"
)
LEGACY_KEYRING_STATE = (
    {'format': 'brisart-identity-tools/bsr2-keyring/v1',
     'kdf': 'BSR2/derive_password_key',
     'iterations': 10000,
     'passphrase': {'salt': 'd5ed8dca8080bded944459ae6a7dec2e844a2fedb9f486bd1c85da37f6f2d977',
                    'wrapped_master_key': {'algorithm': 'BSR2-ARX-SPONGE-ETM',
                                           'version': 2,
                                           'salt': '586e0a76ee280114dcea17efa870f9bc234d35d1d76ecceaf81375fbd3ce5ca9',
                                           'nonce': 'aea68d31c4bf7636d3d576919bdb6340d72c8df8d409a6e8521433efdf0f9c1e',
                                           'ciphertext': '5759a1189dae3f5c3e5140b597c4bd74fbd95bebc73cfc039f4ea5a670730ee5e3e4651b803b133b4e765cd11960ade89cc7ebbf6afaa6652f93052440f435f464648bbdd9999becd312090bcff1f8e61af892710fd9af81e2849ddab7bdfe7ebdc42cdb00fbf6d9a672d15044ae11a73423d4d1c9e5cfe1a593adfa5cbc812e9c92679c3b6445af6d6acba0f5a6449727a828f34d73ecbf47c04beff7090b9fbb7341207a9fb1326bee24a6a813ac1de93b0783b287a8abbff6b34aed0238e991bb923d4067da11eaa7917a5a5c8e6ac9ed9091ea370fadf4becc9212120bdf928551ce55e987356c3acb28dfa50541014840c2b2f99e413c33796e10bafdab',
                                           'tag': '57441362f46a5e9f6b61941cb0686661948f1bcefc19470ca3b0ad85703884a6'}},
     'recovery': {'salt': '0b8a4d2c265e5a7991a34660e853c2f3a165b59f28ebd8ffaa02b0c901b56104',
                  'wrapped_master_key': {'algorithm': 'BSR2-ARX-SPONGE-ETM',
                                         'version': 2,
                                         'salt': '1c396d53729806162a4c09499dd8d95812bb8562e4bc9d520851b4b998c1196a',
                                         'nonce': '3dc81acf6f16e941d7870b4a6eb60952dd0c4b305a38196287cf094ff2d6f0f6',
                                         'ciphertext': '5444a7be4afe31ba244a725402070bc04084b85f3a2d5da2b66d2172e606358b4db70b4da1d4ed92c28ead84cfe1ae6bd92772ba4db391ee45ac8701e9496070d6d260a8b73514338033dd62e176d0bb57ff82a4f1dff3c9e568df870bd733f6b0be2055984bd604aa4478df4752ac7022b95d2162acd13d9360d461f68c5a67ea54af36212a1213b7070d75375ca7e612922f803bbea8357e9c798bc05fa6a0428c6e40787b1caa142b2f41b75e5a8db1600034f466c690e1f33e44a6fdb8d680fd60e7a615eb41c0cec96cc6d55dee5a57a1876747aff5c89db6f8a9c9e70ccfb046b02369b61b94fba554c368f6d83d0f53b6e2493adc949924147b8374c8',
                                         'tag': '56b98f5afb6867751771059cdab9fc82c4c6b76fc580eb146128558bb4af9631'}},
     'master_key_check': '78adf8f1d618625d1a26e28c90eea03120355d821846843a73dd6419bd254e24'}
)


def seal_legacy_bytes(master_key: bytes, plaintext: bytes, context: str) -> dict:
    bsr2 = encryption.require()
    padded = len(plaintext).to_bytes(_LEGACY_LENGTH_PREFIX_BYTES, "big") + plaintext
    padded += bytes(-len(padded) % _LEGACY_PADDING_BYTES)
    return bsr2.envelope.encrypt(master_key, padded, context, new_generator("legacy-fixture"))


def seal_legacy_json(master_key: bytes, payload: dict, context: str) -> dict:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return seal_legacy_bytes(master_key, serialized.encode("utf-8"), context)


def legacy_bind_factor(master_key: bytes, factor_name: str, value: str) -> str:
    primitives = encryption.require().primitives
    name = factor_name.encode("utf-8")
    subkey = primitives.derive_subkey(master_key, name, b"BrisartIdentityTools/factor/v1", 32)
    digest = primitives.keyed_mac(
        subkey, primitives.frame(name) + primitives.frame(value.encode("utf-8")), 32
    )
    return f"bsr2$keyed_mac${factor_name}${primitives.hex_encode(digest)}"


def legacy_keyring_state(passphrase: str, memory_blocks: int = 64):
    """Return ``(state, master_key)`` for a keyring that needs migration only
    because its check value is legacy."""
    primitives = encryption.require().primitives
    keyring, _code = Keyring.create(passphrase, memory_blocks=memory_blocks)
    state = keyring.to_state()
    state["master_key_check"] = {
        "mac": "keyed_mac",
        "value": primitives.hex_encode(primitives.keyed_mac(
            keyring.master_key, b"BrisartIdentityTools/keyring/master-key-check/v1", 32,
        )),
    }
    return state, keyring.master_key
