"""
BrisartOS Instruction Emitter

Pure Python.
No dependencies.
Standard library only.
"""

class Emitter:
    def __init__(self):
        self.code = bytearray()

    def emit(self, *values):
        self.code.extend(values)

    def xor_ax_ax(self):
        self.emit(0x31, 0xC0)

    def mov_ds_ax(self):
        self.emit(0x8E, 0xD8)

    def mov_es_ax(self):
        self.emit(0x8E, 0xC0)

    def lodsb(self):
        self.emit(0xAC)

    def test_al_al(self):
        self.emit(0x84, 0xC0)

    def mov_ah(self, value):
        self.emit(0xB4, value)

    def int10(self):
        self.emit(0xCD, 0x10)

    def hlt(self):
        self.emit(0xF4)

    def get_code(self):
        return bytes(self.code)

    def size(self):
        return len(self.code)