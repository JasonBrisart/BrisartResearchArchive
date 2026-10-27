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
The interface declares abstract methods. Instantiating the abstract class
raises TypeError; a concrete subclass must implement every inherited abstract
method. Runtime device errors belong to the concrete implementation.

Known limitations
-----------------
- No test module imports this file directly; it is exercised only through its
  callers' tests, so check changes manually.

Examples
--------
Concrete subclass skeleton. This example demonstrates the abstract contract,
not a real hardware integration. Replace the method bodies before deployment.
The methods return demonstration values and perform no hardware I/O.

::

    from hardware.base.reader_base import ReaderBase

    class ExampleReaderBase(ReaderBase):
        @property
        def name(self):
            return "Example device"

        def connect(self):
            return True

        def disconnect(self):
            return None

        def health_check(self):
            return True

        def read_card(self):
            return None

    example = ExampleReaderBase()
    assert example.connect() is True
"""

from abc import abstractmethod

from hardware.base.device_base import DeviceBase


class ReaderBase(DeviceBase):

    @abstractmethod
    def read_card(self):
        pass



