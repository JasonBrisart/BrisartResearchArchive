"""
BrisartOS Build Script
Pure Python.
No dependencies.
Standard library only.

This is the single top-level entry point for producing BrisartOS boot
artifacts. It does not implement its own boot sector logic -- it calls
brisartos/boot/make_boot_image.py, which is the one canonical
implementation, so there is exactly one 512-byte machine-code
generator in the project instead of two disagreeing ones.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "boot"))
import make_boot_image


def main():
    make_boot_image.main()


if __name__ == "__main__":
    main()
