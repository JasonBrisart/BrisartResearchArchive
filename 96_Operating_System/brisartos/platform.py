"""
BrisartOS Platform Information
Pure Python.
No dependencies.

This file defines the hardware and compatibility abstraction layer.
The goal is to keep modules stable even when BrisartOS moves across
BIOS, UEFI, x64, ARM, RISC-V, or future hardware targets.
"""


class PlatformInfo:
    def __init__(self):
        self.target = "research-workstation"
        self.word_model = "64-bit host, 128-bit object model"
        self.boot_model = "BIOS prototype, UEFI-first roadmap"
        self.module_abi = "brisartos.module.v1"
        self.dependency_mode = "standard-library-only"

    def describe(self):
        return {
            "target": self.target,
            "word_model": self.word_model,
            "boot_model": self.boot_model,
            "module_abi": self.module_abi,
            "dependency_mode": self.dependency_mode,
        }