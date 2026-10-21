r"""
File: brisartos/host/tests/test_terminal.py

Purpose
-------
Check that the terminal adapter passes prompts, lines, end-of-input and
interrupts through to the host input and print, using patched built-ins.

Verifies: brisartos/host/terminal.py.

Contains 5 test case(s) across 1 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.host.terminal (brisartos/host/terminal.py)
Standard library: contextlib, io, unittest.
Discovered and run by run.py test (and by python -m unittest discover -s
brisartos/host/tests); nothing imports it.

Settings / parameters
---------------------
Inputs and component instances are created inside the individual test methods;
this file defines no shared setUp or tearDown method.

Edge cases
----------
The host input is patched and standard output is captured, so no real terminal
is used. End of input and an interrupt are simulated by raising EOFError and
KeyboardInterrupt.

TerminalTests:
- Read line shows the prompt and returns the line.
- Read line has an empty default prompt.
- End of input and interrupts reach the caller.
- Write line prints text and an empty line.
- Write line converts non text as print does.

Known limitations
-----------------
- No real terminal, encoding or line-editing behavior is exercised.
- Passing proves only the 5 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
Run from the repository root.

::

    python -B -m unittest discover -s brisartos/host/tests -p test_terminal.py
"""
import io
import unittest
from contextlib import redirect_stdout
from unittest import mock

from brisartos.host import terminal


class TerminalTests(unittest.TestCase):
    def test_read_line_shows_the_prompt_and_returns_the_line(self):
        with mock.patch('builtins.input', return_value='hello') as fake:
            self.assertEqual(terminal.read_line('> '), 'hello')
        fake.assert_called_once_with('> ')

    def test_read_line_has_an_empty_default_prompt(self):
        with mock.patch('builtins.input', return_value='x') as fake:
            terminal.read_line()
        fake.assert_called_once_with('')

    def test_end_of_input_and_interrupts_reach_the_caller(self):
        for error in (EOFError, KeyboardInterrupt):
            with mock.patch('builtins.input', side_effect=error):
                with self.assertRaises(error):
                    terminal.read_line()

    def test_write_line_prints_text_and_an_empty_line(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            terminal.write_line('hello')
            terminal.write_line()
        self.assertEqual(buffer.getvalue(), 'hello\n\n')

    def test_write_line_converts_non_text_as_print_does(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            terminal.write_line(5)
        self.assertEqual(buffer.getvalue(), '5\n')


if __name__ == '__main__':
    unittest.main()
