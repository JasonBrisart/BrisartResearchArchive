r"""
File: brisartos/host/terminal.py

Purpose
-------
Read one line from the host terminal and write one line to it, as the single
place product code touches console input and output.

Public interface:
- read_line(prompt='') -- Show the prompt and return the next line typed,
  without its newline.
- write_line(text='') -- Write text followed by a newline; with no argument,
  write an empty line.

Design notes:

These are thin wrappers over the host input and print. They exist so the
architecture audit can forbid those built-ins everywhere else in product code
and so a console can be tested by patching one module. They add no buffering,
encoding policy or line editing.

Communication / relationships
-----------------------------
Standard library: none.
Imported by:
- brisartos/machine/machine.py
- brisartos/shell/console.py
Covered by tests: brisartos/host/tests/test_terminal.py.

Settings / parameters
---------------------
No module-level settings. The prompt and text are supplied by the caller;
streams are whatever the host process has.

Edge cases
----------
End of input raises EOFError and an interrupt raises KeyboardInterrupt; both
reach the caller unchanged. Non-text values given to write_line are converted
by print.

Known limitations
-----------------
- Blocking and single-threaded: read_line waits for the host.
- No terminal editing, history, encoding handling or colour.
- It does not make the console isolated from the host; it only gives the host
  boundary one name.

Examples
--------
Run from the repository root.

::

    from brisartos.host import terminal
    terminal.write_line('hello')
"""
def read_line(prompt=''):
    return input(prompt)


def write_line(text=''):
    print(text)
