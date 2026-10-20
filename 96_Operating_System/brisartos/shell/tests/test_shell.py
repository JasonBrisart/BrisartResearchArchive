r"""
File: brisartos/shell/tests/test_shell.py

Purpose
-------
Exercise shell commands and usage errors through Shell, then compare command
registration, help output and README coverage.

Verifies: brisartos/kernel/kernel.py, brisartos/shell/commands.py,
brisartos/shell/shell.py.

Contains 21 test case(s) across 2 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.kernel.kernel (brisartos/kernel/kernel.py)
- brisartos.shell.commands (brisartos/shell/commands.py)
- brisartos.shell.shell (brisartos/shell/shell.py)
Standard library: pathlib, unittest.
Discovered and run by run.py test (and by python -m unittest discover -s
brisartos/shell/tests); nothing imports it.

Settings / parameters
---------------------
Module fixtures: ROOT.

Fixture helpers in this file: ShellTests: setUp.

Edge cases
----------
Usage errors, tab separators, the settings and update-staging commands,
case-insensitive names, multi-line programs built with append and restore
keeping the logs are all covered.

ShellTests:
- Files round trip.
- Files can be listed by folder.
- Write replaces and append extends with indentation kept.
- Multi line programs can be built and run.
- Python and snapshots.
- Restore keeps the logs.
- Information commands.
- Tabs separate commands and arguments.
- Settings commands.
- Update staging commands.
- Command names are not case sensitive.
- Run module and logs.
- Logs count.
- Tick validation.
- Usage and unknown.
- Unknown command points at help.
- Exit stops kernel.
CommandTableTests:
- The readme documents every command.
- Every command is in the help text.
- Command names are unique and usage starts with the name.
- Every command is reachable through the shell.

Known limitations
-----------------
- The interactive loop is not driven here; it is tested in test_console.py.
- Passing proves only the 21 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
Run from the repository root.

::

    python -B -m unittest discover -s brisartos/shell/tests -p test_shell.py
"""

import unittest
from pathlib import Path

from brisartos.kernel.kernel import Kernel
from brisartos.shell.commands import COMMANDS, ShellError, version_text
from brisartos.shell.shell import Shell

ROOT = Path(__file__).resolve().parents[3]


class ShellTests(unittest.TestCase):
    def setUp(self):
        self.kernel = Kernel(modules_path=ROOT / 'modules')
        self.kernel.start()
        self.shell = Shell(self.kernel)

    def run_lines(self, *lines):
        return [self.shell.execute(line) for line in lines]

    def test_files_round_trip(self):
        out = self.run_lines('write /n.txt hello world', 'read /n.txt', 'files', 'delete /n.txt', 'files')
        self.assertEqual(out[0], '/n.txt')
        self.assertEqual(out[1], 'hello world')
        self.assertIn('/n.txt', out[2])
        self.assertNotIn('/n.txt', out[4])

    def test_files_can_be_listed_by_folder(self):
        self.run_lines('write /a/x.txt one', 'write /b/y.txt two')
        self.assertEqual(self.shell.execute('files /a'), '/a/x.txt')

    def test_write_replaces_and_append_extends_with_indentation_kept(self):
        self.run_lines('write /p.txt first', 'append /p.txt     indented', 'append /p.txt last')
        self.assertEqual(self.kernel.storage.read('/p.txt'), 'first\n    indented\nlast\n')
        self.shell.execute('write /p.txt again')
        self.assertEqual(self.kernel.storage.read('/p.txt'), 'again\n')

    def test_multi_line_programs_can_be_built_and_run(self):
        self.run_lines('write /p.py n = 0', 'append /p.py while n < 3:',
                       'append /p.py     print(n)', 'append /p.py     n = n + 1')
        self.assertEqual(self.shell.execute('python /p.py'), '0\n1\n2')

    def test_python_and_snapshots(self):
        out = self.run_lines('write /p.py print(2 + 3 * 4)', 'python /p.py', 'save s',
                             'delete /p.py', 'restore s', 'read /p.py', 'snapshots')
        self.assertEqual(out[1], '14')
        self.assertEqual(out[5], 'print(2 + 3 * 4)')
        self.assertEqual(out[6], 's')

    def test_restore_keeps_the_logs(self):
        self.run_lines('save s', 'run hello_lab', 'restore s')
        self.assertIn('hello_lab: module finished', self.shell.execute('logs'))
        self.assertNotIn('/modules/hello_lab/hello.txt', self.shell.execute('files'))

    def test_information_commands(self):
        self.assertEqual(self.shell.execute('version'), version_text())
        self.assertIn('settings - online', self.shell.execute('services'))
        self.assertIn('class: Settings', self.shell.execute('service settings'))
        self.assertIn('hello_lab', self.shell.execute('modules'))
        self.assertIn('author: Jason Brisart', self.shell.execute('describe hello_lab'))
        self.assertIn('state: running', self.shell.execute('system'))
        self.assertEqual(self.shell.execute('devices'), 'console')
        self.assertEqual(len(self.shell.execute('new-id')), 32)
        self.assertIn('loaded: hello_lab', self.shell.execute('reload'))
        self.assertEqual(self.shell.execute(''), '')
        self.assertEqual(self.shell.execute('   '), '')

    def test_tabs_separate_commands_and_arguments(self):
        self.shell.execute('write\t/t.txt\thello there')
        self.assertEqual(self.shell.execute('read\t/t.txt'), 'hello there')
        self.shell.execute('append /t.txt\t    indented')
        self.assertEqual(self.kernel.storage.read('/t.txt'), 'hello there\n    indented\n')

    def test_settings_commands(self):
        self.assertEqual(self.shell.execute('set theme plain dark'), 'theme = plain dark')
        self.assertEqual(self.shell.execute('get theme'), 'plain dark')
        self.assertIn('theme: plain dark', self.shell.execute('settings'))
        self.assertEqual(self.shell.execute('unset theme'), 'removed')
        with self.assertRaises(KeyError):
            self.shell.execute('get theme')
        with self.assertRaises(ShellError):
            self.shell.execute('set onlykey')

    def test_update_staging_commands(self):
        self.shell.execute('write /patch.py x = 1')
        self.assertEqual(self.shell.execute('stage first /patch.py'), 'staged first')
        self.assertEqual(self.shell.execute('staged'), 'first')
        self.assertEqual(self.kernel.services.get('updates').inspect('first')['source'], 'x = 1\n')
        self.assertEqual(self.shell.execute('discard first'), 'discarded')
        self.assertEqual(self.shell.execute('staged'), '')
        with self.assertRaises(ShellError):
            self.shell.execute('stage onlyname')

    def test_command_names_are_not_case_sensitive(self):
        self.assertEqual(self.shell.execute('VERSION'), version_text())

    def test_run_module_and_logs(self):
        self.assertIn('hello_lab wrote', self.shell.execute('run hello_lab'))
        self.assertIn('hello_lab: module finished', self.shell.execute('logs'))

    def test_logs_count(self):
        for _ in range(5):
            self.kernel.events.record('probe', 'x')
        self.assertEqual(len(self.shell.execute('logs 2').splitlines()), 2)
        for bad in ('logs 0', 'logs -1', 'logs x', 'logs 1 2'):
            with self.assertRaises(ShellError):
                self.shell.execute(bad)

    def test_tick_validation(self):
        self.assertEqual(self.shell.execute('tick'), '0')
        self.assertEqual(self.shell.execute('tick 5'), '0')
        for bad in ('tick x', 'tick -1', 'tick 1 2'):
            with self.assertRaises(ShellError):
                self.shell.execute(bad)

    def test_usage_and_unknown(self):
        for line in ('bogus', 'read', 'read a b', 'write /only-path', 'write', 'append /only-path',
                     'run a b', 'save', 'files a b'):
            with self.assertRaises(ShellError):
                self.shell.execute(line)

    def test_unknown_command_points_at_help(self):
        with self.assertRaises(ShellError) as caught:
            self.shell.execute('bogus')
        self.assertIn("type 'help'", str(caught.exception))

    def test_exit_stops_kernel(self):
        self.assertEqual(self.shell.execute('exit'), 'stopped')
        with self.assertRaises(RuntimeError):
            self.shell.execute('help')


class CommandTableTests(unittest.TestCase):
    def test_the_readme_documents_every_command(self):
        readme = (ROOT / 'brisartos' / 'shell' / 'README.md').read_text(encoding='utf-8')
        for name, usage, summary, _ in COMMANDS:
            self.assertIn('| `' + usage + '` |', readme, usage)

    def test_every_command_is_in_the_help_text(self):
        kernel = Kernel()
        kernel.start()
        help_text = Shell(kernel).execute('help')
        for name, usage, summary, _ in COMMANDS:
            self.assertIn(usage, help_text)
            self.assertIn(summary, help_text)

    def test_command_names_are_unique_and_usage_starts_with_the_name(self):
        names = [name for name, _, _, _ in COMMANDS]
        self.assertEqual(len(names), len(set(names)))
        for name, usage, _, _ in COMMANDS:
            self.assertTrue(usage.split()[0] == name, usage)

    def test_every_command_is_reachable_through_the_shell(self):
        kernel = Kernel()
        kernel.start()
        shell = Shell(kernel)
        self.assertEqual(sorted(shell._handlers), sorted(name for name, _, _, _ in COMMANDS))


if __name__ == '__main__':
    unittest.main()
