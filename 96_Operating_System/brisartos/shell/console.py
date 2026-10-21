r"""
File: brisartos/shell/console.py

Purpose
-------
Run the interactive console with startup and banner output inside the cleanup
scope, carrying commands through the text-console device.

Public interface:
- serve(kernel, shell) -- Process queued console lines and return drained
  output.
- main(argv=None) -- Start disk or memory mode, serve input and clean up on
  exit.

Design notes:

The kernel handles failed-start cleanup. The console finally block stops a
running kernel after startup, banner or input-loop failure. Command exceptions
become device error lines; base exceptions propagate after cleanup.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.host.system (brisartos/host/system.py)
- brisartos.host.terminal (brisartos/host/terminal.py)
- brisartos.kernel.kernel (brisartos/kernel/kernel.py)
- brisartos.shell.commands (brisartos/shell/commands.py)
- brisartos.shell.shell (brisartos/shell/shell.py)
Standard library: none.
Imported by:
- run.py
Covered by tests: brisartos/shell/tests/test_console.py.

Settings / parameters
---------------------
- USAGE = 'usage: console [--memory]' -- The line printed for an unrecognised
  option.

Edge cases
----------
Any option other than none or --memory prints the usage line and returns 2
without starting a kernel.

- serve() catches EOFError -- An empty device queue ends serving; it means
  every queued line has been handled, not that the session is over.
- serve() catches Exception -- Reports a failed command as one error line on
  the console device and keeps the session alive.
- main() catches (EOFError, KeyboardInterrupt) -- End of input or Ctrl+C at the
  prompt ends the loop cleanly instead of printing a traceback.

Known limitations
-----------------
- Terminal input and output go through brisartos/host/terminal.py, which still
  wraps the host input and print.
- Cleanup hooks have no timeout and final logging can fail; inspect
  kernel.shutdown_errors.

Examples
--------
Run from the repository root.

::

    python -B run.py start --memory
"""

from ..host import system, terminal
from ..kernel.kernel import Kernel
from .commands import version_text
from .shell import Shell

USAGE = 'usage: console [--memory]'


def serve(kernel, shell):
    while kernel.state == 'running':
        try:
            line = kernel.console.read()
        except EOFError:
            break
        try:
            output = shell.execute(line)
        except Exception as error:
            kernel.console.write('error: ' + type(error).__name__ + ': ' + str(error))
        else:
            if output:
                kernel.console.write(output)
    return kernel.console.drain()


def main(argv=None):
    argv = system.command_line_arguments() if argv is None else list(argv)
    if argv not in ([], ['--memory']):
        terminal.write_line(USAGE)
        return 2
    memory = argv == ['--memory']
    kernel = Kernel(data_root=None if memory else 'data', modules_path='modules')
    try:
        kernel.start()
        shell = Shell(kernel)
        terminal.write_line(version_text() + ' - storage: ' + ('memory (discarded on exit)' if memory else 'data/'))
        terminal.write_line('Runs on host Python; this is not a firmware or hypervisor boot. Type help.')
        for label, reason in sorted(kernel.modules.failures.items()):
            terminal.write_line('module ' + label + ' not loaded: ' + reason)
        while kernel.state == 'running':
            try:
                line = terminal.read_line('BrisartOS> ')
            except (EOFError, KeyboardInterrupt):
                terminal.write_line()
                break
            kernel.console.feed(line)
            for text in serve(kernel, shell):
                terminal.write_line(text)
    finally:
        if kernel.state == 'running':
            kernel.stop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
