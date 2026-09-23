# BrisartOS Python-Made Hardware Architecture

BrisartOS is designed as a Python-made operating system project.

The project does not begin with a C kernel, assembly source tree, Linux distribution, GRUB configuration, or external OS framework.

Instead, BrisartOS begins with Python source that generates the raw binary structures required to boot hardware.

---

## Core Model

```text
Python builder scripts
        ↓
Generated binary boot image
        ↓
Firmware loads boot sector
        ↓
Generated BrisartOS code executes
        ↓
Future Brisart runtime loads
```

---

## Why Python Generates Bytes

Hardware cannot execute Python syntax directly during firmware boot.

The CPU executes machine instructions. Therefore, a Python-made OS must use Python to generate the machine-readable boot structures.

This keeps the project Python-authored while still producing hardware-executable output.

---

## Phase 0

The first phase is a 512-byte boot sector generated entirely by Python.

It proves:

- The project can create bootable hardware-level output
- No assembler is required for the first milestone
- No C compiler is required for the first milestone
- No external OS build system is required for the first milestone

---

## Future Architecture

Possible future layers:

1. Python boot image generator
2. Python binary layout tools
3. Python-defined instruction emitters
4. Python-generated protected-mode transition
5. Python-generated kernel runtime
6. Brisart shell
7. Brisart filesystem tools
8. Brisart archive and preservation commands
9. Brisart identity verification commands
10. Hardware-installable research environment
