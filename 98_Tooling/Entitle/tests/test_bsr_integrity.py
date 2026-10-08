"""
BSR2 vendor integrity test.

The project's core claim is that the four BrisartSecurityResearch (BSR2) modules
under ``vendor/`` are used *completely unmodified* -- byte-for-byte identical to
their upstream release. The CHANGELOG asserts this; this test enforces it, so the
claim is checked by CI rather than trusted.

If BSR2 is ever intentionally updated to a new upstream release, regenerate the
pinned hashes below from the new files (and record the change in the CHANGELOG).
An *unexpected* mismatch means a vendored cryptographic file changed without going
through that process -- which is exactly what this test exists to catch.

To regenerate after a deliberate upstream update:
    python -c "import hashlib,pathlib; \\
        [print(p.name, hashlib.sha256(p.read_bytes()).hexdigest()) \\
         for p in sorted(pathlib.Path('vendor').glob('brisart_security_*.py'))]"
"""
import hashlib
from pathlib import Path

VENDOR_DIR = Path(__file__).resolve().parent.parent / "vendor"

# Pinned SHA-256 of each vendored BSR2 module. These correspond to the specific
# upstream BSR2 release vendored into this repository.
PINNED_HASHES = {
    "brisart_security_primitives.py":
        "953f4148fa4f840f5bf944cf2ece8d7ecf51b9d7dee10cfee73589ce3f16b65f",
    "brisart_security_drbg.py":
        "0781ecf75d3c71c6cb7b469c3eff5343f493852a8d092a728599dd99b463a9d1",
    "brisart_security_entropy.py":
        "29245cbb4ff8fa7bf106ef0d06ffc8258624f0dad36fc50587108927ec1d8168",
    "brisart_security_envelope.py":
        "e352dac9f600566b1021b1c6f34f9c53034b8491e98bdb020f97102a9b62d33a",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestVendorIntegrity:
    def test_all_pinned_files_exist(self):
        for name in PINNED_HASHES:
            assert (VENDOR_DIR / name).is_file(), f"missing vendored file: {name}"

    def test_vendored_files_match_pinned_hashes(self):
        for name, expected in PINNED_HASHES.items():
            actual = _sha256(VENDOR_DIR / name)
            assert actual == expected, (
                f"BSR2 vendored file '{name}' does not match its pinned SHA-256. "
                f"Expected {expected}, got {actual}. If this change was intentional "
                f"(a deliberate upstream BSR2 update), regenerate the pinned hashes "
                f"and note it in the CHANGELOG."
            )

    def test_no_unexpected_bsr_modules_present(self):
        # Guard against an extra brisart_security_*.py sneaking into vendor/ that
        # isn't covered by a pinned hash.
        present = {p.name for p in VENDOR_DIR.glob("brisart_security_*.py")}
        assert present == set(PINNED_HASHES), (
            f"vendor/ BSR2 modules {present} do not match the pinned set "
            f"{set(PINNED_HASHES)}."
        )
