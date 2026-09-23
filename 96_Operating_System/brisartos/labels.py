"""
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