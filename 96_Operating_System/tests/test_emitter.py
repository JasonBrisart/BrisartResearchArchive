"""
tests/test_emitter.py

Purpose
-------
Unit tests for `brisartos/emitter.py` (`Emitter`). `Emitter` is a tiny,
stateful byte-buffer wrapper that boot-image code generators use to build up
raw 8086 machine code one instruction at a time. These tests pin down the
exact opcode bytes each helper method must emit, since a single wrong byte
here would silently produce a boot sector that either does the wrong thing
on real hardware or fails the `tests/boot_sector_test.py` emulator with a
confusing "unsupported opcode" error far from the actual mistake.

Communication relationships
----------------------------
`Emitter` is not currently imported by `brisartos/boot/make_boot_image.py`
(that file inlines its own raw byte literals instead), but it models the
same 8086 instruction subset that both `make_boot_image.py` and
`tests/boot_sector_test.py`'s `BootSectorCPU` understand. Keeping this test
file's expected opcodes in lockstep with those two files is what makes
`Emitter` safe to adopt as the shared code-generation path in a future
boot-image refactor without silently drifting from what the emulator (and
real firmware) actually expects.

Settings / parameters
----------------------
No constructor parameters exist on `Emitter`; each test constructs a fresh
instance so that byte-buffer state never leaks between test cases.

Edge-case behavior
-------------------
- `get_code()` must return an immutable `bytes` object (not the internal
  mutable `bytearray`), so callers cannot accidentally mutate an emitter's
  internal state through the value they read back.
- `size()` must always equal `len(get_code())`, including for a brand-new,
  empty emitter (size 0).
- `emit()` accepts a variable number of raw byte values directly and must
  preserve call order exactly, since instruction encoding is
  order-sensitive.
"""
import unittest

from _support import add_brisartos_dir_to_syspath

add_brisartos_dir_to_syspath()

from emitter import Emitter  # noqa: E402


class EmitterTests(unittest.TestCase):
    def test_new_emitter_is_empty(self):
        emitter = Emitter()
        self.assertEqual(emitter.get_code(), b"")
        self.assertEqual(emitter.size(), 0)

    def test_get_code_returns_bytes_not_bytearray(self):
        emitter = Emitter()
        emitter.emit(0x90)
        self.assertIsInstance(emitter.get_code(), bytes)

    def test_emit_preserves_order_and_raw_values(self):
        emitter = Emitter()
        emitter.emit(0x01, 0x02, 0x03)
        emitter.emit(0x04)
        self.assertEqual(emitter.get_code(), b"\x01\x02\x03\x04")
        self.assertEqual(emitter.size(), 4)

    def test_xor_ax_ax_opcode(self):
        emitter = Emitter()
        emitter.xor_ax_ax()
        self.assertEqual(emitter.get_code(), b"\x31\xC0")

    def test_mov_ds_ax_opcode(self):
        emitter = Emitter()
        emitter.mov_ds_ax()
        self.assertEqual(emitter.get_code(), b"\x8E\xD8")

    def test_mov_es_ax_opcode(self):
        emitter = Emitter()
        emitter.mov_es_ax()
        self.assertEqual(emitter.get_code(), b"\x8E\xC0")

    def test_lodsb_opcode(self):
        emitter = Emitter()
        emitter.lodsb()
        self.assertEqual(emitter.get_code(), b"\xAC")

    def test_test_al_al_opcode(self):
        emitter = Emitter()
        emitter.test_al_al()
        self.assertEqual(emitter.get_code(), b"\x84\xC0")

    def test_mov_ah_opcode_with_immediate(self):
        emitter = Emitter()
        emitter.mov_ah(0x0E)
        self.assertEqual(emitter.get_code(), b"\xB4\x0E")

    def test_int10_opcode(self):
        emitter = Emitter()
        emitter.int10()
        self.assertEqual(emitter.get_code(), b"\xCD\x10")

    def test_hlt_opcode(self):
        emitter = Emitter()
        emitter.hlt()
        self.assertEqual(emitter.get_code(), b"\xF4")

    def test_sequence_matches_a_realistic_print_loop(self):
        """
        Regression check: chaining helpers in the same order the real boot
        sector uses (xor/mov segregs, then a lodsb/test/mov-ah/int10/hlt
        tail) must byte-for-byte match hand-encoded 8086 machine code.
        """
        emitter = Emitter()
        emitter.xor_ax_ax()
        emitter.mov_ds_ax()
        emitter.mov_es_ax()
        emitter.lodsb()
        emitter.test_al_al()
        emitter.mov_ah(0x0E)
        emitter.int10()
        emitter.hlt()
        expected = b"\x31\xC0\x8E\xD8\x8E\xC0\xAC\x84\xC0\xB4\x0E\xCD\x10\xF4"
        self.assertEqual(emitter.get_code(), expected)
        self.assertEqual(emitter.size(), len(expected))


if __name__ == "__main__":
    unittest.main()
