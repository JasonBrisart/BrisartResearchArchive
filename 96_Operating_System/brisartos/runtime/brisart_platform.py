"""
BrisartOS Platform Abstraction
Pure Python.
No dependencies.

This file represents the future-hardware strategy.
Modules should target the BrisartOS module ABI, not raw CPU or firmware details.
"""


class PlatformInfo:
    def __init__(self):
        self.os_name = "BrisartOS"
        self.platform_profile = "research-workstation"
        self.boot_model = "BIOS prototype with UEFI-first roadmap"
        self.cpu_model = "64-bit host target"
        self.object_model = "128-bit internal identifiers"
        self.module_abi = "brisartos.module.v1"
        self.dependency_policy = "python-standard-library-only"
        self.module_policy = "pure-python-modules-only"
        self.future_hardware_policy = "replaceable boot and hardware layers"

    def describe(self):
        return {
            "os_name": self.os_name,
            "platform_profile": self.platform_profile,
            "boot_model": self.boot_model,
            "cpu_model": self.cpu_model,
            "object_model": self.object_model,
            "module_abi": self.module_abi,
            "dependency_policy": self.dependency_policy,
            "module_policy": self.module_policy,
            "future_hardware_policy": self.future_hardware_policy,
        }