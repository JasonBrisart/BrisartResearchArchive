"""
File: v1/tests/support.py

Purpose
-------
Shared helpers for the v1 test suite: put v1/ on sys.path, install the
stand-in package that v1's robots module needs, and provide a
deterministic random source and a fuzz-volume multiplier.

Communication / relationships
-----------------------------
Standard library: os, random, sys, types, importlib.util, pathlib.
Imported by every test file in this folder; never imported by a v1
product module.

Settings / parameters
---------------------
- BRISART_FUZZ_SCALE (environment variable, default 1) -- Multiplies the
  number of random cases each fuzz test runs.
- BRISART_SEED (environment variable, default 20261021) -- Base seed; each
  test derives its own seed from it, so failures are reproducible.

Edge cases
----------
v1/brisart_robots.py imports brisart_ai.native.brisart_url inside
can_fetch(), a package path that does not exist in this repository. This
helper registers brisart_ai and brisart_ai.native as empty packages and
points brisart_ai.native.brisart_url at v1/brisart_url.py, so the module
runs exactly as written without being edited.

Known limitations
-----------------
The stand-in package is process-wide; run each version's tests in its own
`unittest discover` invocation, as the README commands do.

Examples
--------
::

    python -B -m unittest discover -s v1/tests
"""

import importlib.util
import os
import random
import sys
import types
from pathlib import Path

V1 = Path(__file__).resolve().parents[1]
if str(V1) not in sys.path:
    sys.path.insert(0, str(V1))

SCALE = max(1, int(os.environ.get("BRISART_FUZZ_SCALE", "1")))
BASE_SEED = int(os.environ.get("BRISART_SEED", "20261021"))


def _install_url_shim():
    if "brisart_ai.native.brisart_url" in sys.modules:
        return
    spec = importlib.util.spec_from_file_location("brisart_ai.native.brisart_url", V1 / "brisart_url.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    package = types.ModuleType("brisart_ai")
    native = types.ModuleType("brisart_ai.native")
    package.__path__ = []
    native.__path__ = []
    package.native = native
    native.brisart_url = module
    sys.modules.update({"brisart_ai": package, "brisart_ai.native": native,
                        "brisart_ai.native.brisart_url": module})


_install_url_shim()


def scaled(count):
    return count * SCALE


def rng(label):
    return random.Random(BASE_SEED * 1000003 + sum(ord(c) * (i + 1) for i, c in enumerate(label)))


def random_bytes(r, n):
    return bytes(r.getrandbits(8) for _ in range(n))
