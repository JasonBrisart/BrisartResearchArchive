"""
File: packages/demo.py

Purpose
-------
The package demo shared by the CLI (`packages.main`'s `demo` command) and the
GUI (`gui.tabs.tab_packages.PackagesTab`'s "Run Demo" button): a complete, real
create -> add-recipient -> open -> validate-custody cycle with freshly
generated passphrases, run in memory and returned as a transcript. One owner,
so the CLI and the GUI cannot drift apart.

Public interface:
- run_demo() -- Run the cycle and return {"transcript", "package_id"}.

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.encryption (crypto/encryption.py) -- entropy for demo passphrases
- packages.ciphers (packages/ciphers.py) -- text_master_key, the same
  typed-text derivation the CLI and GUI use
- packages.package (packages/package.py)
Standard library: secrets (demo package id only).
Imported by:
- gui/tabs/tab_packages.py
- packages/main.py
Covered by tests: packages/tests/test_demo.py.

Settings / parameters
---------------------
None.

Edge cases
----------
- Raises EncryptionNotFoundError when Brisart Encryption is not linked; the
  CLI reports it with exit status 3 and the GUI in an error dialog.
- Otherwise raises nothing and catches nothing of its own.

Known limitations
-----------------
- Nothing is written to disk; the package and passphrases are discarded with
  the transcript. (Official adds a save-to-disk variant; LTS does not.)

Examples
--------
::

    from packages.demo import run_demo
    print("\n".join(run_demo()["transcript"]))
"""

import secrets

from crypto import encryption
from packages import ciphers
from packages import package as ibp_package


def run_demo() -> dict:
    """Run a full create -> add-recipient -> open -> validate-custody cycle
    in memory with freshly generated passphrases.

    Returns a dict with keys:
        "transcript": list[str] -- one line per demo step, for display.
        "package_id": str
    """
    package_id = f"demo-{secrets.token_hex(4)}"
    entropy = encryption.require().entropy
    alice_key = ciphers.text_master_key(entropy.system_entropy(16).hex())
    bob_key = ciphers.text_master_key(entropy.system_entropy(16).hex())
    transcript = [f"creating package {package_id!r} with recipient 'alice'..."]

    state = ibp_package.create_package(
        package_id, "Alice", {"message": "hello from the demo package"},
        {"alice": ("Alice", alice_key)},
    )
    transcript.append("adding recipient 'bob' (authorized by alice)...")
    state = ibp_package.add_recipient(state, "bob", "Bob", bob_key, "alice", alice_key)

    transcript.append("opening the package as 'bob'...")
    payload, state = ibp_package.open_package(state, "bob", bob_key)
    transcript.append(f"bob opened the package and read: {payload!r}")

    transcript.append("verifying the custody chain...")
    ibp_package.validate_package(state)
    for entry in ibp_package.custody_summary(state):
        transcript.append(f"  {entry['recorded_at']}  {entry['action']:<20} {entry['actor_label']}")
    transcript.append("demo complete: custody chain is intact.")
    return {"transcript": transcript, "package_id": package_id}
