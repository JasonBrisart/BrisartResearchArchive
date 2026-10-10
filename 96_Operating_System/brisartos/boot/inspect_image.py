"""
File: brisartos/boot/inspect_image.py

Purpose
-------
Inspect a BrisartOS boot image using Python only.

Communication / relationships
-----------------------------
Direct module imports: pathlib, sys.

Settings / parameters
---------------------
No uppercase module-level settings are declared; parameters remain defined in the code below.

Edge cases
----------
Additional edge-case guarantees are not established by this header; existing implementation and tests remain unchanged.

Known limitations
-----------------
This header update does not establish complete behavioral, platform, or security validation.

Examples
--------
Inspect the definitions below and the project documentation for supported usage.
"""

from pathlib import Path
import sys
def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python brisartos/inspect_image.py <image>")
        raise SystemExit(2)
    path = Path(sys.argv[1])
    data = path.read_bytes()
    print(f"file: {path}")
    print(f"size: {len(data)} bytes")
    print(f"boot signature: {data[-2:].hex() if len(data) >= 2 else 'missing'}")
    print(f"valid 512-byte boot sector: {len(data) == 512 and data[-2:] == b'\\x55\\xaa'}")
    print("first 64 bytes:", data[:64].hex(" "))
if __name__ == "__main__":
    main()

