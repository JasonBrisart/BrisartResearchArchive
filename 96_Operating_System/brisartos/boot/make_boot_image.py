"""Build the first BrisartOS boot image using Python only.

This script writes a 512-byte BIOS boot sector image. It does not call an
assembler, compiler, linker, GRUB, Linux build system, or external package.

The boot image is intentionally tiny: it prints a BrisartOS message using BIOS
video interrupt 0x10 and then halts forever.

Bare-metal safety notes
-----------------------
Two things the BIOS spec does NOT guarantee, but real firmware
variance can violate, are handled explicitly here rather than assumed:

1. Stack validity. SS:SP is not guaranteed to be usable on entry.
   `int 0x10` pushes FLAGS/CS/IP onto whatever stack SS:SP points at;
   if it is garbage, that push can corrupt arbitrary memory, including
   this boot sector itself. A stack is set up explicitly before any
   interrupt is invoked.

2. CS normalization. Firmware may hand off control as either
   CS:IP = 0000:7C00 or 07C0:0000 -- both point at the same physical
   address (0x7C00) but change what every absolute offset in this
   sector means. A direct far jump pins CS to 0 immediately, so every
   later absolute address computed as BOOT_LOAD_ADDRESS + offset is
   guaranteed correct regardless of which convention the firmware used.
"""
from pathlib import Path

BOOT_LOAD_ADDRESS = 0x7C00
IMAGE_SIZE = 512
SIGNATURE = b"\x55\xAA"
OUTPUT = Path("build/brisartos_boot.img")

# Stack grows downward from the boot sector's own load address. The
# 512 bytes below 0x7C00 (down to conventional memory's low end) are
# unused at boot time, so this is safe, standard practice for a
# first-stage boot sector that only needs a few words of stack depth.
STACK_TOP = 0x7C00

MESSAGE = (
    "BrisartOS PYBOOT 0.1.0-alpha\r\n"
    "Python-made bare-metal boot image\r\n"
    "Local-first. Custom. Offline-capable.\r\n"
)


def rel8(source_after_operand: int, target: int) -> int:
    value = target - source_after_operand
    if not -128 <= value <= 127:
        raise ValueError(f"relative jump out of range: {value}")
    return value & 0xFF


def build_boot_sector() -> bytes:
    code = bytearray()

    # Mask interrupts while the stack and segment registers are in an
    # inconsistent state, so a stray hardware interrupt can't fire
    # mid-setup and push onto an invalid stack.
    code += b"\xFA"          # cli

    # Clear AX, then point DS and ES at segment 0.
    code += b"\x31\xC0"      # xor ax, ax
    code += b"\x8E\xD8"      # mov ds, ax
    code += b"\x8E\xC0"      # mov es, ax

    # Establish a known-good stack before anything (including the far
    # jump below, which does not itself need one, but int 0x10 later
    # does) can rely on SS:SP.
    code += b"\x8E\xD0"      # mov ss, ax
    code += b"\xBC" + STACK_TOP.to_bytes(2, "little")  # mov sp, STACK_TOP

    # Stack is valid again; safe to take interrupts.
    code += b"\xFB"          # sti

    # LODSB advances SI using the direction flag; DF is not guaranteed
    # clear at boot, so set it explicitly rather than assume forward.
    code += b"\xFC"          # cld

    # Far jump to normalize CS:IP to segment 0, pinned to an absolute
    # address computed below once we know where the next instruction
    # lands. This protects every subsequent absolute offset in this
    # sector against the 0000:7C00 vs 07C0:0000 firmware ambiguity.
    far_jump_index = len(code)
    code += b"\xEA\x00\x00\x00\x00"  # jmp 0x0000:0x0000 (patched below)

    continue_here = len(code)

    # Patch SI after we know where the message will land.
    mov_si_index = len(code)
    code += b"\xBE\x00\x00"  # mov si, imm16

    print_loop = len(code)
    code += b"\xAC"          # lodsb
    code += b"\x84\xC0"      # test al, al
    jz_index = len(code)
    code += b"\x74\x00"      # jz hang
    code += b"\xB4\x0E"      # mov ah, 0x0e
    code += b"\xCD\x10"      # int 0x10
    jmp_index = len(code)
    code += b"\xEB\x00"      # jmp print_loop

    hang = len(code)
    code += b"\xF4"          # hlt
    code += b"\xEB\xFD"      # jmp hang

    # Patch the far jump target: segment 0, offset = absolute address
    # of continue_here.
    continue_target = BOOT_LOAD_ADDRESS + continue_here
    code[far_jump_index + 1] = continue_target & 0xFF
    code[far_jump_index + 2] = (continue_target >> 8) & 0xFF
    code[far_jump_index + 3] = 0x00
    code[far_jump_index + 4] = 0x00

    message_offset = BOOT_LOAD_ADDRESS + len(code)
    code[mov_si_index + 1] = message_offset & 0xFF
    code[mov_si_index + 2] = (message_offset >> 8) & 0xFF

    code[jz_index + 1] = rel8(jz_index + 2, hang)
    code[jmp_index + 1] = rel8(jmp_index + 2, print_loop)

    message = MESSAGE.encode("ascii") + b"\x00"
    sector = code + message

    if len(sector) > IMAGE_SIZE - 2:
        raise ValueError("boot sector is too large")

    sector += b"\x00" * ((IMAGE_SIZE - 2) - len(sector))
    sector += SIGNATURE

    if len(sector) != IMAGE_SIZE:
        raise AssertionError("boot sector must be exactly 512 bytes")
    if sector[-2:] != SIGNATURE:
        raise AssertionError("boot sector signature missing")

    return bytes(sector)


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    sector = build_boot_sector()
    OUTPUT.write_bytes(sector)
    print(f"wrote {OUTPUT} ({len(sector)} bytes)")
    print(f"signature: {sector[-2:].hex()}")


if __name__ == "__main__":
    main()