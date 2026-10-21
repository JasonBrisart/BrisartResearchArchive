"""
File: v3/tests/support.py

Purpose
-------
Shared helpers for the v3 test suite: import-path setup, a deterministic
random source per test, a fuzz-volume multiplier, a best-of-N timer that
pauses the garbage collector, and a linear-growth assertion.

Communication / relationships
-----------------------------
Standard library: gc, os, random, sys, time, pathlib.
Imported by every test file in this folder; never imported by a v3
product module.

Settings / parameters
---------------------
- BRISART_FUZZ_SCALE (environment variable, default 1) -- Multiplies the
  number of random cases each fuzz test runs, for longer campaigns.
- BRISART_SEED (environment variable, default 20261021) -- Base seed;
  each test derives its own seed from it, so failures are reproducible.

Edge cases
----------
Timing checks use the best of several runs and generous ratios, and
pause the cyclic garbage collector while measuring, because allocating
many small objects makes it do work that is not the code under test.

Known limitations
-----------------
Wall-clock timing can still be disturbed by an extremely loaded machine.
The growth checks prove nothing about absolute speed.

Examples
--------
::

    BRISART_FUZZ_SCALE=10 python -B -m unittest discover -s v3/tests
"""

import gc
import os
import random
import sys
import time
from pathlib import Path

V3 = Path(__file__).resolve().parents[1]
if str(V3) not in sys.path:
    sys.path.insert(0, str(V3))

SCALE = max(1, int(os.environ.get("BRISART_FUZZ_SCALE", "1")))
BASE_SEED = int(os.environ.get("BRISART_SEED", "20261021"))


def scaled(count):
    return count * SCALE


def rng(label):
    return random.Random(BASE_SEED * 1000003 + sum(ord(c) * (i + 1) for i, c in enumerate(label)))


def random_bytes(r, n):
    return bytes(r.getrandbits(8) for _ in range(n))


def best_time(function, repeats=3):
    best = None
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        for _ in range(repeats):
            started = time.perf_counter()
            function()
            elapsed = time.perf_counter() - started
            best = elapsed if best is None or elapsed < best else best
    finally:
        if was_enabled:
            gc.enable()
    return best


def assert_roughly_linear(test, make_input, run, small=1, large=4, factor=3.0, floor=0.002):
    """Fail if `large` times the input costs more than factor * large times the small input."""
    small_input, large_input = make_input(small), make_input(large)
    t_small = max(best_time(lambda: run(small_input)), floor)
    t_large = best_time(lambda: run(large_input))
    ratio = t_large / t_small
    test.assertLess(ratio, (large / small) * factor,
                    "growth ratio %.1f for %dx input suggests super-linear time" % (ratio, large // small))
