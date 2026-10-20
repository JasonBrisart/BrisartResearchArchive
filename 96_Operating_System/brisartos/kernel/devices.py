r"""
File: brisartos/kernel/devices.py

Purpose
-------
Keep named device objects in DeviceRegistry and provide TextConsole as separate
input and output queues of strings.

Public interface:
- class DeviceRegistry -- A name-to-device table.
- DeviceRegistry.register(name, device) -- Add a device under a unique
  non-empty name.
- DeviceRegistry.get(name) -- Return a registered device or raise
  CapabilityUnavailable.
- DeviceRegistry.names() -- Return the sorted device names.
- class TextConsole -- An input queue and an output list of text lines.
- TextConsole.feed(text) -- Queue a line of input.
- TextConsole.read() -- Remove and return the oldest queued input line.
- TextConsole.write(text) -- Append a line to the output list.
- TextConsole.output() -- Return a copy of the output list.
- TextConsole.drain() -- Remove and return every output line written so far.

Design notes:

Registration rejects empty or duplicate names and a None device, but does not
impose a device protocol. TextConsole consumes input in arrival order and
returns a copy of its output list; drain hands the pending lines to the reader
and empties the list, so a long session does not accumulate output. These
objects model registration and queued text; they do not implement terminal
access or hardware drivers.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.kernel.platform (brisartos/kernel/platform.py)
Standard library: none.
Imported by:
- brisartos/kernel/kernel.py
Covered by tests: brisartos/kernel/tests/test_components.py.

Settings / parameters
---------------------
No module-level settings. Device names must be unique; the console keeps its
queues as lists.

Edge cases
----------
A duplicate or empty name, or a missing device object, raises ValueError.
Reading an empty console raises EOFError. Non-text input or output raises
TypeError.

- DeviceRegistry.register() raises ValueError: "unique device name required"
- DeviceRegistry.register() raises ValueError: "device object required"
- DeviceRegistry.get() raises CapabilityUnavailable: "No Python device adapter
  registered: {...}"
- TextConsole.feed() raises TypeError: "console input must be text"
- TextConsole.read() raises EOFError: "no queued console input"
- TextConsole.write() raises TypeError: "console output must be text"

Known limitations
-----------------
- No hardware drivers exist: registering a device does not give access to
  hardware.
- The input queue, and output that is never drained, are unbounded; neither
  queue is thread-safe.

Examples
--------
Run from the repository root.

::

    from brisartos.kernel.devices import DeviceRegistry, TextConsole

    devices = DeviceRegistry()
    console = TextConsole()
    devices.register('console', console)
    console.feed('hello')
    assert devices.get('console').read() == 'hello'
    console.write('ready')
    assert console.output() == ['ready']
"""

from .platform import CapabilityUnavailable


class DeviceRegistry:
    def __init__(self):
        self._devices = {}

    def register(self, name, device):
        if not isinstance(name, str) or not name or name in self._devices:
            raise ValueError('unique device name required')
        if device is None:
            raise ValueError('device object required')
        self._devices[name] = device

    def get(self, name):
        if name not in self._devices:
            raise CapabilityUnavailable('No Python device adapter registered: ' + str(name))
        return self._devices[name]

    def names(self):
        return sorted(self._devices)


class TextConsole:
    def __init__(self):
        self._input = []
        self._output = []

    def feed(self, text):
        if not isinstance(text, str):
            raise TypeError('console input must be text')
        self._input.append(text)

    def read(self):
        if not self._input:
            raise EOFError('no queued console input')
        return self._input.pop(0)

    def write(self, text):
        if not isinstance(text, str):
            raise TypeError('console output must be text')
        self._output.append(text)

    def output(self):
        return list(self._output)

    def drain(self):
        lines, self._output = self._output, []
        return lines
