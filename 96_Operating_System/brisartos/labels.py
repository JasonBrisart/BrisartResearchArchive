"""
File: brisartos/labels.py

Purpose
-------
Simple label resolver for BrisartOS.

Communication / relationships
-----------------------------
No direct module-level imports are declared.

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

Additional module documentation
-------------------------------
Simple label resolver for BrisartOS.

Pure Python.
No dependencies.
"""

class Labels:
    def __init__(self):
        self.labels = {}
        self.fixups = []

    def define(self, name, offset):
        self.labels[name] = offset

    def add_fixup(self, name, source_offset):
        self.fixups.append((name, source_offset))

    def patch(self, image):
        image = bytearray(image)

        for name, source in self.fixups:
            target = self.labels[name]

            relative = target - (source + 1)

            if relative < -128 or relative > 127:
                raise ValueError(
                    f"Jump out of range: {name}"
                )

            image[source] = relative & 0xFF

        return bytes(image)
