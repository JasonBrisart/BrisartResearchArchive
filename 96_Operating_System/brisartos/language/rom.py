r"""
File: brisartos/language/rom.py

Purpose
-------
Wrap a parsed source program in a reset, running, halted or faulted lifecycle
and expose execution results through copied snapshots.

Public interface:
- class SourceROMMachine -- A source program with an explicit lifecycle and
  honest capability flags.
- SourceROMMachine(source=DEFAULT_ROM, max_steps=10000, max_source_chars=65536)
  -- Validate and parse the source once, at construction.
- SourceROMMachine.source -- Property. The program text, read-only.
- SourceROMMachine.reset() -- Return to the reset state and clear results;
  refused while running.
- SourceROMMachine.boot() -- Run the program from the reset state and return a
  snapshot.
- SourceROMMachine.snapshot() -- Return the state, variables, output, steps,
  fault, boot count and the capability flags.
- main() -- Boot the built-in program once and print its report; this is what
  python run.py rom runs.

Design notes:

Construction checks source size and interpreter limits, then parses once. boot
creates a fresh interpreter, increments the attempt counter and captures
partial results even when execution raises. reset clears results but preserves
the source and attempt count. The model explicitly reports that it performs no
hardware boot and is not a full or self-hosted runtime.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.language.interpreter (brisartos/language/interpreter.py)
- brisartos.language.parser (brisartos/language/parser.py)
Standard library: none.
Imported by:
- run.py
Covered by tests: brisartos/language/tests/test_rom.py.

Settings / parameters
---------------------
- DEFAULT_ROM = 'print("BrisartOS source-ROM model")\nready = True\n' -- The
  built-in program run by python run.py rom.

Edge cases
----------
Bad source or limits raise TypeError, ValueError or LanguageError at
construction. Booting twice without reset() raises RuntimeError, and so does
reset() while running.

- SourceROMMachine.__init__() raises TypeError: "ROM source must be text"
- SourceROMMachine.__init__() raises ValueError: "max_source_chars must be a
  positive integer"
- SourceROMMachine.__init__() raises ValueError: "ROM exceeds source-size
  policy"
- SourceROMMachine.reset() raises RuntimeError: "cannot reset while running"
- SourceROMMachine.boot() raises RuntimeError: "reset required before boot"
- SourceROMMachine.boot() re-raises the active exception
- SourceROMMachine.boot() catches Exception -- Records the fault as the machine
  state and text, then re-raises so the caller still sees the original error.

Known limitations
-----------------
- A lifecycle model only: it does not boot hardware, replace Python or host
  itself.
- The program is limited to the restricted language and its step budget.

Examples
--------
Run from the repository root.

::

    from brisartos.language.rom import SourceROMMachine

    machine = SourceROMMachine('x = 4\nprint(x)')
    report = machine.boot()
    assert report['output'] == ['4'] and report['hardware_boot'] is False
    machine.reset()
    assert machine.boot()['boot_attempts'] == 2
"""

from .interpreter import Interpreter
from .parser import parse

DEFAULT_ROM = 'print("BrisartOS source-ROM model")\nready = True\n'


class SourceROMMachine:
    def __init__(self, source=DEFAULT_ROM, max_steps=10000, max_source_chars=65536):
        if not isinstance(source, str):
            raise TypeError('ROM source must be text')
        if type(max_source_chars) is not int or max_source_chars < 1:
            raise ValueError('max_source_chars must be a positive integer')
        if len(source) > max_source_chars:
            raise ValueError('ROM exceeds source-size policy')
        Interpreter(max_steps)
        self._nodes = parse(source)
        self._source = source
        self._max_steps = max_steps
        self._state = 'reset'
        self._variables = {}
        self._output = []
        self._steps = 0
        self._fault = None
        self._boots = 0

    @property
    def source(self):
        return self._source

    def reset(self):
        if self._state == 'running':
            raise RuntimeError('cannot reset while running')
        self._state = 'reset'
        self._variables = {}
        self._output = []
        self._steps = 0
        self._fault = None

    def boot(self):
        if self._state != 'reset':
            raise RuntimeError('reset required before boot')
        engine = Interpreter(self._max_steps)
        self._state = 'running'
        self._boots += 1
        try:
            engine.execute(self._nodes)
        except Exception as exc:
            self._state = 'faulted'
            self._fault = type(exc).__name__ + ': ' + str(exc)
            raise
        else:
            self._state = 'halted'
        finally:
            self._variables = dict(engine.variables)
            self._output = list(engine.output)
            self._steps = engine.steps
        return self.snapshot()

    def snapshot(self):
        return dict(state=self._state, variables=dict(self._variables),
                    output=list(self._output), steps=self._steps, fault=self._fault,
                    boot_attempts=self._boots, execution='restricted-source model on host Python',
                    hardware_boot=False, full_python=False, self_hosting=False)


def main():
    report = SourceROMMachine().boot()
    for line in report['output']:
        print(line)
    print('State:', report['state'])
    print('Hardware boot:', report['hardware_boot'])
    print('Full Python:', report['full_python'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
