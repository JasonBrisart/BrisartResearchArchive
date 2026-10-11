"""
File: hardware/card_readers/placeholder_reader.py

Purpose
-------
Stand-in ReaderBase implementation that performs no hardware I/O and returns
fixed values. It lets the hardware manager, registry, and callers be wired and
exercised end-to-end before a real card reader is attached.

Public interface:
- class PlaceholderReader(ReaderBase). Public methods: name, connect,
  disconnect, health_check, read_card.

Communication / relationships
-----------------------------
Depends on (project modules):
- hardware.base.reader_base (hardware/base/reader_base.py)
Standard library: none.
Imported by: no other module in this tree imports it directly.
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
- Placeholder reader implementation.
- Not a real device driver: methods return fixed values and perform no hardware
  I/O. Use it for wiring/tests until a concrete driver exists.
- No test module imports this file directly; it is exercised only through its
  callers' tests, so check changes manually.

Examples
--------
::

    from hardware.card_readers.placeholder_reader import PlaceholderReader
    obj = PlaceholderReader()
    obj.name
"""

from hardware.base.reader_base import ReaderBase


class PlaceholderReader(ReaderBase):

    @property
    def name(self):
        return "Placeholder Reader"

    def connect(self):
        return True

    def disconnect(self):
        pass

    def health_check(self):
        return True

    def read_card(self):
        return None



