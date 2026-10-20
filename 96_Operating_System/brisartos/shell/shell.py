r"""
File: brisartos/shell/shell.py

Purpose
-------
Dispatch one command line to a registered handler after checking that the bound
kernel is running.

Public interface:
- class Shell -- A command interpreter bound to one kernel.
- Shell(kernel) -- Bind a kernel and build the dispatch dictionary from the
  command table once.
- Shell.execute(line) -- Run one line and return the text to show; a blank line
  returns an empty string.

Design notes:

Construction copies COMMANDS into a name-to-handler dictionary. execute ignores
blank input, lowercases the command word and passes the untouched remainder
from the first separator to the handler. It neither prints results nor catches
handler failures, and later additions to COMMANDS do not update an existing
Shell.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.shell.commands (brisartos/shell/commands.py)
Standard library: none.
Imported by:
- brisartos/shell/console.py
Covered by tests: brisartos/shell/tests/test_console.py,
brisartos/shell/tests/test_shell.py.

Settings / parameters
---------------------
No module-level settings.

Edge cases
----------
A stopped kernel raises RuntimeError. An unknown command raises ShellError
pointing at help.

- Shell.execute() raises RuntimeError: "kernel is not running"
- Shell.execute() raises ShellError: "unknown command: {...} (type 'help')"

Known limitations
-----------------
- There is no history, completion or scripting; one command per call.

Examples
--------
Run from the repository root.

::

    from brisartos.kernel.kernel import Kernel
    from brisartos.shell.shell import Shell

    kernel = Kernel()
    kernel.start()
    shell = Shell(kernel)
    shell.execute('write /n.txt hello world')
    assert shell.execute('read /n.txt') == 'hello world'
"""

from .commands import COMMANDS, ShellError


class Shell:
    def __init__(self, kernel):
        self.kernel = kernel
        self._handlers = {name: handler for name, _, _, handler in COMMANDS}

    def execute(self, line):
        if self.kernel.state != 'running':
            raise RuntimeError('kernel is not running')
        parts = line.strip().split(None, 1)
        if not parts:
            return ''
        name = parts[0]
        text = line.lstrip()[len(name):]
        handler = self._handlers.get(name.lower())
        if handler is None:
            raise ShellError('unknown command: ' + name + " (type 'help')")
        return handler(self.kernel, text)
