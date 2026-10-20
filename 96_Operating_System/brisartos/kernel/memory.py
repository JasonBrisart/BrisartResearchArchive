r"""
File: brisartos/kernel/memory.py

Purpose
-------
Associate arbitrary objects with monotonically increasing integer handles,
enforcing a limit on the number of live entries.

Public interface:
- class ObjectMemory -- A capacity-limited table of objects addressed by
  handle.
- ObjectMemory(capacity=1024) -- Create a table that holds at most capacity
  objects.
- ObjectMemory.allocate(value) -- Store a value and return its new handle.
- ObjectMemory.read(handle) -- Return the object stored under a handle.
- ObjectMemory.write(handle, value) -- Replace the object stored under an
  existing handle.
- ObjectMemory.release(handle) -- Remove an object and return it.
- ObjectMemory.status() -- Return {used, capacity}.

Design notes:

Allocation increments a counter that release never rewinds. Reads and writes
require an exact int handle, excluding booleans, and return or replace the
stored reference. Capacity measures dictionary entries rather than bytes; this
is an object table, not physical memory allocation.

Communication / relationships
-----------------------------
Standard library: none.
Imported by:
- brisartos/kernel/kernel.py
Covered by tests: brisartos/kernel/tests/test_components.py.

Settings / parameters
---------------------
ObjectMemory(capacity=1024) limits the number of objects, not their size.

Edge cases
----------
A full table raises MemoryError; an unknown or non-integer handle raises
KeyError; a capacity that is not a positive integer raises ValueError at
construction.

- ObjectMemory.__init__() raises ValueError: "capacity must be a positive
  integer"
- ObjectMemory.allocate() raises MemoryError: "logical object capacity
  exhausted"
- ObjectMemory._validate() raises KeyError: "unknown object handle"

Known limitations
-----------------
- There is no paging, byte accounting or isolation between holders of a handle.
- Stored values are not copied, so changing an object changes what every holder
  of its handle sees.
- No caller outside the tests uses this table yet.

Examples
--------
Run from the repository root.

::

    from brisartos.kernel.memory import ObjectMemory

    memory = ObjectMemory(capacity=2)
    handle = memory.allocate('one')
    memory.write(handle, 'two')
    assert memory.release(handle) == 'two'
    assert memory.status() == {'used': 0, 'capacity': 2}
"""

class ObjectMemory:
    def __init__(self, capacity=1024):
        if type(capacity) is not int or capacity < 1:
            raise ValueError('capacity must be a positive integer')
        self.capacity = capacity
        self._next = 1
        self._objects = {}

    def allocate(self, value):
        if len(self._objects) >= self.capacity:
            raise MemoryError('logical object capacity exhausted')
        handle = self._next
        self._next += 1
        self._objects[handle] = value
        return handle

    def _validate(self, handle):
        if type(handle) is not int or handle not in self._objects:
            raise KeyError('unknown object handle')

    def read(self, handle):
        self._validate(handle)
        return self._objects[handle]

    def write(self, handle, value):
        self._validate(handle)
        self._objects[handle] = value

    def release(self, handle):
        self._validate(handle)
        return self._objects.pop(handle)

    def status(self):
        return {'used': len(self._objects), 'capacity': self.capacity}
