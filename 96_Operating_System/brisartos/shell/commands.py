r"""
File: brisartos/shell/commands.py

Purpose
-------
Define shell command handlers and their ordered registration table, together
with usage parsing and text-formatting helpers.

Public interface:
- class ShellError(ValueError) -- Raised for wrong usage and unknown commands;
  a ValueError.
- version_text() -- Return the product name, a space and the release version.
- command(name, usage, summary) -- Decorator factory: register a handler under
  a name with a usage line and a summary.
- words(text, count, usage) -- Split text into exactly count words or raise
  ShellError with the usage line.
- path_and_text(text, usage) -- Split a first word from the rest of the line,
  keeping the rest verbatim so indentation survives.
- lines(mapping) -- Format a mapping as key: value lines.

Design notes:

The command decorator appends usage, summary and handler records to COMMANDS.
Help reads that table, while handlers call the supplied kernel. words enforces
exact argument counts; path_and_text removes one separator after a path and
preserves the remaining text. Handlers return display text and generally let
component exceptions propagate.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.host.system (brisartos/host/system.py)
- version (version.py)
Standard library: none.
Imported by:
- brisartos/shell/console.py
- brisartos/shell/shell.py
Covered by tests: brisartos/shell/tests/test_console.py,
brisartos/shell/tests/test_shell.py.

Settings / parameters
---------------------
- PRODUCT = 'BrisartOS' -- The product name shown next to the version.
- COMMANDS = [] -- The ordered list of (name, usage, summary, handler) built by
  the decorator.
- DEFAULT_LOG_LINES = 20 -- How many events the logs command shows when no
  count is given.

Edge cases
----------
Wrong argument counts, a missing text for write or append, a missing value for
set, and a bad count for tick or logs raise ShellError with a usage line.

- words() raises ShellError: "usage: {...}"
- path_and_text() raises ShellError: "usage: {...}"
- list_files() raises ShellError: "usage: files [FOLDER]"
- get_setting() raises KeyError: "unknown setting: {...}"
- tick() raises ShellError: "usage: tick [COUNT]"
- show_logs() raises ShellError: "usage: logs [COUNT]"

Known limitations
-----------------
- One line per command: there is no quoting, piping or multi-line input, so
  programs are built a line at a time with write and append.
- set stores its value as text; the settings service can hold any object but
  the shell cannot express one.
- read shows a file without its final newline, so a file that ends without one
  cannot be distinguished from one that ends with one.

Examples
--------
Run from the repository root.

::

    from brisartos.shell.commands import COMMANDS

    names = [name for name, usage, summary, handler in COMMANDS]
    assert 'help' in names and 'run' in names
    assert len(names) == len(set(names))
"""

from version import __version__
from ..host import system

PRODUCT = 'BrisartOS'
COMMANDS = []
DEFAULT_LOG_LINES = 20


class ShellError(ValueError):
    pass


def version_text():
    return PRODUCT + ' ' + __version__


def command(name, usage, summary):
    def register(handler):
        COMMANDS.append((name, usage, summary, handler))
        return handler
    return register


def words(text, count, usage):
    parts = text.split()
    if len(parts) != count:
        raise ShellError('usage: ' + usage)
    return parts


def path_and_text(text, usage):
    text = text.lstrip()
    end = 0
    while end < len(text) and not text[end].isspace():
        end += 1
    path, body = text[:end], text[end + 1:]
    if not path or not body:
        raise ShellError('usage: ' + usage)
    return path, body


def lines(mapping):
    return '\n'.join(str(key) + ': ' + str(value) for key, value in mapping.items())


@command('help', 'help', 'show this list')
def show_help(kernel, text):
    width = max(len(usage) for _, usage, _, _ in COMMANDS)
    rows = ['  ' + usage.ljust(width) + '  ' + summary for _, usage, summary, _ in COMMANDS]
    return 'commands:\n' + '\n'.join(rows)


@command('version', 'version', 'show the release identifier')
def show_version(kernel, text):
    return version_text()


@command('system', 'system', 'describe the kernel')
def show_system(kernel, text):
    return lines(kernel.describe())


@command('files', 'files [FOLDER]', 'list files, optionally under one folder')
def list_files(kernel, text):
    parts = text.split()
    if len(parts) > 1:
        raise ShellError('usage: files [FOLDER]')
    return '\n'.join(kernel.storage.list_files(parts[0] if parts else '/'))


@command('read', 'read PATH', 'show a file')
def read_file(kernel, text):
    content = kernel.storage.read(words(text, 1, 'read PATH')[0])
    return content[:-1] if content.endswith('\n') else content


@command('write', 'write PATH TEXT', 'create or replace a file with one line (indentation is kept)')
def write_file(kernel, text):
    path, body = path_and_text(text, 'write PATH TEXT')
    return kernel.storage.write(path, body + '\n')


@command('append', 'append PATH TEXT', 'add one line to the end of a file (indentation is kept)')
def append_file(kernel, text):
    path, body = path_and_text(text, 'append PATH TEXT')
    return kernel.storage.append(path, body + '\n')


@command('delete', 'delete PATH', 'delete a file')
def delete_file(kernel, text):
    kernel.storage.delete(words(text, 1, 'delete PATH')[0])
    return 'deleted'


@command('python', 'python PATH', 'run a file with the restricted language')
def run_python(kernel, text):
    return '\n'.join(kernel.run_file(words(text, 1, 'python PATH')[0])['output'])


@command('save', 'save NAME', 'snapshot all files except logs')
def save_snapshot(kernel, text):
    kernel.services.get('archive').save(words(text, 1, 'save NAME')[0])
    return 'saved'


@command('restore', 'restore NAME', 'put a snapshot back (logs are kept)')
def restore_snapshot(kernel, text):
    kernel.services.get('archive').restore(words(text, 1, 'restore NAME')[0])
    return 'restored'


@command('snapshots', 'snapshots', 'list saved snapshots')
def list_snapshots(kernel, text):
    return '\n'.join(kernel.services.get('archive').names())


@command('services', 'services', 'list services and their status')
def list_services(kernel, text):
    return '\n'.join(name + ' - ' + kernel.services.describe(name)['status']
                     for name in kernel.services.names())


@command('service', 'service NAME', 'describe one service')
def describe_service(kernel, text):
    return lines(kernel.services.describe(words(text, 1, 'service NAME')[0]))


@command('modules', 'modules', 'list modules')
def list_modules(kernel, text):
    return '\n'.join(kernel.modules.names())


@command('describe', 'describe NAME', 'describe one module')
def describe_module(kernel, text):
    return lines(kernel.modules.describe(words(text, 1, 'describe NAME')[0]))


@command('run', 'run NAME', 'run a module')
def run_module(kernel, text):
    result = kernel.modules.run(words(text, 1, 'run NAME')[0])
    return '' if result is None else str(result)


@command('reload', 'reload', 'rediscover modules in the modules folder')
def reload_modules(kernel, text):
    failures = kernel.reload_modules()
    rows = ['loaded: ' + ', '.join(kernel.modules.names())]
    rows += ['not loaded: ' + label + ' (' + reason + ')' for label, reason in sorted(failures.items())]
    return '\n'.join(rows)


@command('settings', 'settings', 'list every setting')
def list_settings(kernel, text):
    return lines(kernel.services.get('settings').snapshot())


@command('get', 'get KEY', 'show one setting')
def get_setting(kernel, text):
    key = words(text, 1, 'get KEY')[0]
    settings = kernel.services.get('settings')
    if key not in settings.snapshot():
        raise KeyError('unknown setting: ' + key)
    return str(settings.get(key))


@command('set', 'set KEY VALUE', 'store a setting as text (memory only)')
def set_setting(kernel, text):
    key, value = path_and_text(text, 'set KEY VALUE')
    kernel.services.get('settings').set(key, value)
    return key + ' = ' + value


@command('unset', 'unset KEY', 'remove a setting')
def unset_setting(kernel, text):
    kernel.services.get('settings').delete(words(text, 1, 'unset KEY')[0])
    return 'removed'


@command('stage', 'stage NAME PATH', 'stage a file as an update candidate (never applied)')
def stage_update(kernel, text):
    name, path = words(text, 2, 'stage NAME PATH')
    kernel.services.get('updates').stage(name, kernel.storage.read(path))
    return 'staged ' + name


@command('staged', 'staged', 'list staged update candidates')
def list_staged(kernel, text):
    return '\n'.join(kernel.services.get('updates').names())


@command('discard', 'discard NAME', 'drop a staged update candidate')
def discard_update(kernel, text):
    kernel.services.get('updates').discard(words(text, 1, 'discard NAME')[0])
    return 'discarded'


@command('devices', 'devices', 'list devices')
def list_devices(kernel, text):
    return '\n'.join(kernel.devices.names())


@command('tasks', 'tasks', 'show scheduler tasks')
def show_tasks(kernel, text):
    return lines(kernel.scheduler.status())


@command('tick', 'tick [COUNT]', 'give the scheduler COUNT steps (default 1)')
def tick(kernel, text):
    parts = text.split()
    if len(parts) > 1 or (parts and not parts[0].isdigit()):
        raise ShellError('usage: tick [COUNT]')
    return str(kernel.scheduler.run(int(parts[0]) if parts else 1))


@command('logs', 'logs [COUNT]', 'show the most recent kernel events (default 20)')
def show_logs(kernel, text):
    parts = text.split()
    if len(parts) > 1 or (parts and not (parts[0].isdigit() and int(parts[0]) > 0)):
        raise ShellError('usage: logs [COUNT]')
    count = int(parts[0]) if parts else DEFAULT_LOG_LINES
    return '\n'.join(event['time'] + ' ' + event['source'] + ': ' + event['message']
                     for event in kernel.events.recent(count))


@command('new-id', 'new-id', 'print a random 32-character identifier')
def new_id(kernel, text):
    return system.new_id()


@command('exit', 'exit', 'stop the kernel and leave')
def stop_kernel(kernel, text):
    kernel.stop()
    return 'stopped'
