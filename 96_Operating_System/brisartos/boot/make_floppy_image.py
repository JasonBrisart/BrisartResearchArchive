"""
BrisartOS Floppy Image Builder
Pure Python.
No dependencies.
Standard library only.

This wraps the 512-byte BrisartOS boot sector into a 1.44 MB
floppy-style image for legacy BIOS VM testing.
"""
from pathlib import Path

BOOT_SECTOR = Path("build/brisartos_boot.img")
OUTPUT = Path("build/brisartos_boot.vfd")
FLOPPY_SIZE = 1_474_560
BOOT_SIZE = 512
SIGNATURE = b"\x55\xAA"


def build_floppy_image():
    if not BOOT_SECTOR.exists():
        raise FileNotFoundError(
            "Missing boot sector. Run: python brisartos/boot/make_boot_image.py"
        )
    boot = BOOT_SECTOR.read_bytes()
    if len(boot) != BOOT_SIZE:
        raise ValueError("Boot sector must be exactly 512 bytes")
    if boot[-2:] != SIGNATURE:
        raise ValueError("Boot sector missing 55AA signature")
    image = bytearray(FLOPPY_SIZE)
    image[:BOOT_SIZE] = boot
    return bytes(image)


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image = build_floppy_image()
    OUTPUT.write_bytes(image)
    print()
    print("===================================")
    print(" BrisartOS Floppy Image Complete")
    print("===================================")
    print(f"Input  : {BOOT_SECTOR}")
    print(f"Output : {OUTPUT}")
    print(f"Size   : {len(image)} bytes")
    print("Boot sector copied to first 512 bytes")
    print("Signature: 55AA")
    print()


if __name__ == "__main__":
    main()
