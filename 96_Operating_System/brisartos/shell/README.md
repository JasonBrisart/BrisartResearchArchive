# Command Shell and Console

`commands.py`, `shell.py` and `console.py` separate command definitions, line dispatch and interactive input/output.

## `commands.py`: registered handlers

`@command(name, usage, summary)` appends a handler record to `COMMANDS`. `help` reads that table. `version_text()` combines the product name with the imported release version. `words()` checks exact argument counts, `path_and_text()` splits a path from preserved text, and `lines()` formats mappings.

The following table describes the handlers implemented in this file. References to component results describe what a handler returns, not an implementation of that component here.


| Command | Purpose | Output and errors |
| --- | --- | --- |
| `help` | Show every command | `commands:` and one line per command |
| `version` | Show the release version | The product name and the version |
| `system` | Describe the kernel | Seven `key: value` lines; see [the kernel](../kernel/README.md) |
| `files [FOLDER]` | List files, optionally under one folder | Sorted paths; nothing for an empty or unknown folder |
| `read PATH` | Show a file | The text without its final newline; `FileNotFoundError` if missing |
| `write PATH TEXT` | Create or replace a file with one line | The normalized path; the file becomes `TEXT` plus a newline |
| `append PATH TEXT` | Add one line to the end of a file | The path; leading spaces in `TEXT` are kept |
| `delete PATH` | Delete a file | `deleted`, or `FileNotFoundError` |
| `python PATH` | Run a file with the restricted language | Its printed lines; `LanguageError`, or Python errors such as `ZeroDivisionError` |
| `save NAME` | Snapshot every file except the logs | `saved` |
| `restore NAME` | Put a snapshot back; the logs are kept | `restored`, or `KeyError: unknown snapshot: NAME` |
| `snapshots` | List saved snapshots | Names, one per line |
| `services` | List services and their status | `NAME - online` per service |
| `service NAME` | Describe one service | `name`, `version`, `status` and `class` |
| `modules` | List modules | Names, one per line |
| `describe NAME` | Describe one module | `name`, `display_name`, `permissions`, `description`, `author`, `version` and `origin` |
| `run NAME` | Run a module | Its return value as text; `KeyError` for an unknown module |
| `reload` | Rediscover modules in the modules folder | `loaded: a, b`, then one `not loaded: FOLDER (REASON)` line per failure |
| `settings` | List every setting | `key: value` lines |
| `get KEY` | Show one setting | The value; `KeyError: unknown setting: KEY` |
| `set KEY VALUE` | Store a setting as text | `KEY = VALUE`; spaces in `VALUE` are kept |
| `unset KEY` | Remove a setting | `removed` |
| `stage NAME PATH` | Stage a file as an update candidate (never applied) | `staged NAME` |
| `staged` | List staged update candidates | Names, one per line |
| `discard NAME` | Drop a staged update candidate | `discarded` |
| `devices` | List devices | Names, one per line |
| `tasks` | Show scheduler tasks | `ID: {...}` lines; empty from the console |
| `tick [COUNT]` | Give the scheduler COUNT steps (default 1) | The number of steps performed |
| `logs [COUNT]` | Show the most recent kernel events (default 20) | `TIME SOURCE: MESSAGE` lines for this session |
| `new-id` | Print a random 32-character identifier | 32 hexadecimal characters |
| `exit` | Stop the kernel and leave | `stopped` |


Wrong usage generally raises `ShellError`; errors from called components retain their own types. Handlers without argument validation can ignore extra text, so not every extra argument is rejected. `tick` and `logs` accept digit strings before converting them with `int`; unusual digit characters can still fail conversion.

`write` and `append` add a newline. Their parser removes one separator after the path and preserves the remaining body, including indentation. `read` removes one final newline from display output, so its display is not an exact representation of file termination.

## `shell.py`: one dispatch operation

`Shell(kernel)` copies the command table into a dispatch dictionary. `execute(line)` requires a running kernel, ignores blank input, matches the command word case-insensitively and passes the remaining text to its handler. Unknown commands raise `ShellError` with a help hint. The shell returns text and does not print or catch failures.

There is no quoting, piping, completion or multiline parser. A command table modified after Shell construction does not update that existing instance.

## Building a stored program through handlers

```text
BrisartOS> write /count.py n = 0
BrisartOS> append /count.py while n < 3:
BrisartOS> append /count.py     print(n)
BrisartOS> append /count.py     n = n + 1
BrisartOS> python /count.py
```

The extra spaces after the path become program indentation. The final handler returns three output lines: 0, 1 and 2. The command named `python` invokes the restricted language, not an unrestricted interpreter.

## `console.py`: input loop and cleanup

`main(argv=None)` accepts no options or `--memory`; other options print usage and return 2. It constructs a kernel using relative `data` and `modules` paths, starts it, prints the banner and discovery failures, then reads lines at the prompt. Each line is fed to the kernel's console device and handed to `serve(kernel, shell)`, which reads queued lines back from the device, runs them through `Shell` and writes each result or error line to the device; the loop prints what `serve` drained.

An `Exception` raised by a command becomes the line `error: TYPE: message` and leaves the session running. EOF or an interrupt at the prompt ends the loop. A base exception from command execution is not swallowed. Once the loop's try/finally has been entered, a still-running kernel is stopped on exit.

Kernel startup and banner printing are now inside the cleanup scope. Kernel itself unwinds failed startup; a still-running kernel is stopped when the console exits. Shutdown errors are retained in kernel.shutdown_errors rather than skipping later cleanup. Non-returning hooks remain outside any timeout guarantee.

The terminal is still read with `input()` and written with `print()`; the device carries the session between them. Relative paths depend on the working directory; the root router supplies the project root when launching it.

## Local tests

`tests/test_shell.py` exercises dispatch, handlers, usage, help and this command table. `tests/test_console.py` calls `serve` directly to check that lines, results and errors pass through the device, and launches real child consoles to check errors, EOF, options, persistence, memory mode and module-exit cleanup. Terminal editing and interactive interrupt delivery are not exercised.

## Updated state contracts

Disk mode persists settings, snapshots and candidates under /system. Memory mode discards them. Snapshots exclude /logs and /system. Service descriptions include state and persistent; module descriptions include API requirements. Recent log display retains its text format while events carry kind/details in memory.
