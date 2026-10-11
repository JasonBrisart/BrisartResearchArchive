"""
File: hardware/base/reader_base.py

Purpose
-------
Abstract interface for access-card readers. Extends DeviceBase with the
card-reading operation that concrete readers (PC/SC, placeholder) must
implement.

Public interface:
- class ReaderBase(DeviceBase). Public methods: read_card.

Communication / relationships
-----------------------------
Depends on (project modules):
- hardware.base.device_base (hardware/base/device_base.py)
Standard library: abc.
Imported by:
- hardware/card_readers/pcsc_reader.py
- hardware/card_readers/placeholder_reader.py
Covered by tests: no test file imports this module directly.

Settings / parameters
---------------------
No module-level constants, environment variables, or defaulted arguments:
behaviour is controlled entirely by the values callers pass in.

Edge cases
----------
Defines no error paths of its own: it raises nothing and catches nothing, so
any exception from the standard library or a dependency reaches the caller
unchanged.

Known limitations
-----------------
- No test module imports this file directly; it is exercised only through its
  callers' tests, so check changes manually.

Examples
--------
::

    from hardware.base.reader_base import ReaderBase
    obj = ReaderBase()
    obj.read_card()
"""

from abc import abstractmethod

from hardware.base.device_base import DeviceBase


class ReaderBase(DeviceBase):

    @abstractmethod
    def read_card(self):
        pass



