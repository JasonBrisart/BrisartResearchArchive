r"""
File: brisartos/kernel/platform.py

Purpose
-------
Report fixed execution capabilities and raise CapabilityUnavailable for
unsupported boot-media and firmware-handoff requests.

Public interface:
- class CapabilityUnavailable(RuntimeError) -- Raised when something asks for a
  capability BrisartOS does not have.
- class Platform -- The declared facts about the execution environment.
- Platform.describe() -- Return a fresh dictionary of those facts, including
  bootable False.
- Platform.boot_media() -- Always raise CapabilityUnavailable: BrisartOS cannot
  produce boot media.
- Platform.firmware_handoff() -- Always raise CapabilityUnavailable: BrisartOS
  has no firmware handoff.

Design notes:

describe returns a fresh dictionary rather than inspecting the current machine.
Both boot-related methods unconditionally raise the same project exception
type. The flags and refusals are the complete implementation, not placeholders
for an undisclosed boot path.

Communication / relationships
-----------------------------
Standard library: none.
Imported by:
- brisartos/kernel/devices.py
- brisartos/kernel/kernel.py
Covered by tests: brisartos/kernel/tests/test_components.py.

Settings / parameters
---------------------
No module-level settings. The facts are fixed in Platform.describe.

Edge cases
----------
boot_media() and firmware_handoff() always raise; there is no condition under
which they succeed.

- Platform.boot_media() raises CapabilityUnavailable: "BrisartOS cannot produce
  boot media"
- Platform.firmware_handoff() raises CapabilityUnavailable: "BrisartOS has no
  firmware handoff"

Known limitations
-----------------
- The description is a declaration, not a probe: it does not inspect the
  machine.
- Nothing here makes BrisartOS bootable. The refusals are the whole
  implementation.

Examples
--------
Run from the repository root.

::

    from brisartos.kernel.platform import Platform, CapabilityUnavailable

    assert Platform().describe()['bootable'] is False
    try:
        Platform().boot_media()
    except CapabilityUnavailable:
        pass
    else:
        raise AssertionError('boot media must be refused')
"""

class CapabilityUnavailable(RuntimeError):
    pass


class Platform:
    def describe(self):
        return {'execution': 'host Python interpreter', 'hardware_target': None,
                'bootable': False, 'native_codegen': False,
                'third_party_packages': False}

    def boot_media(self):
        raise CapabilityUnavailable('BrisartOS cannot produce boot media')

    def firmware_handoff(self):
        raise CapabilityUnavailable('BrisartOS has no firmware handoff')
