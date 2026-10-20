r"""
File: brisartos/shell/console.py

Purpose
-------
Run the interactive BrisartOS console, choosing storage mode, reporting
module-load failures and carrying each command and its result through the
kernel's console device.

Public interface:
- serve(kernel, shell) -- Run every line queued on the kernel's console device
  through the shell and return the output lines it produced.
- main(argv=None) -- Run the console; return 0 normally, or 2 for an
  unrecognised option.

Design notes:

main accepts no options or --memory, creates and starts a kernel, then enters
the input loop. Each terminal line is fed to the kernel's TextConsole device;
serve reads it back from the device, executes it and writes the result or the
error line to the device, and the loop prints what serve drained. An Exception
from a command is displayed without ending the session; EOFError and
KeyboardInterrupt at the prompt end it. The finally block stops a running
kernel after the loop has been entered. Startup occurs before that block, so
startup failures do not receive the same cleanup guarantee.

brisartos/shell/tests/test_console.py calls serve directly and also drives main
in child processes, which the static relationship lines cannot show.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.host.system (brisartos/host/system.py)
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
- One line at a time from standard input; line editing and history are whatever
  the terminal provides.
- The terminal itself is still read with input() and written with print(); the
  device carries the session between them, not the terminal I/O.
- Kernel startup and banner printing occur before the loop cleanup block; an
  exception there is not covered by its finally clause.

Examples
--------
Run from the repository root.

::

    python -B run.py start --memory
"""

from ..host import system
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
        print(USAGE)
        return 2
    memory = argv == ['--memory']
    kernel = Kernel(data_root=None if memory else 'data', modules_path='modules')
    kernel.start()
    shell = Shell(kernel)
    print(version_text() + ' - storage: ' + ('memory (discarded on exit)' if memory else 'data/'))
    print('Runs on host Python; this is not a firmware or hypervisor boot. Type help.')
    for label, reason in sorted(kernel.modules.failures.items()):
        print('module ' + label + ' not loaded: ' + reason)
    try:
        while kernel.state == 'running':
            try:
                line = input('BrisartOS> ')
            except (EOFError, KeyboardInterrupt):
                print()
                break
            kernel.console.feed(line)
            for text in serve(kernel, shell):
                print(text)
    finally:
        if kernel.state == 'running':
            kernel.stop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
