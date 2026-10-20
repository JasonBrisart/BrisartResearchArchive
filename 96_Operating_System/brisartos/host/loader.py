r"""
File: brisartos/host/loader.py

Purpose
-------
Discover immediate child folders containing module.py and execute an individual
entry file into a fresh module object.

Public interface:
- module_files(folder) -- Return the NAME/module.py files directly under
  folder, in alphabetical order; a missing folder, loose files and folders
  without module.py are ignored.
- load_module(path) -- Execute one module file with importlib and return the
  resulting module object.

Design notes:

Discovery sorts directory entries and ignores loose files and child folders
without the entry file. Loading constructs an import specification and executes
it without explicitly inserting the new object into sys.modules. The file is
executed before its declarations can be inspected; this loader performs no
permission or compatibility validation.

Communication / relationships
-----------------------------
Standard library: importlib, pathlib.
Imported by:
- brisartos/modules/registry.py
Covered by tests: brisartos/host/tests/test_loader.py.

Settings / parameters
---------------------
- ENTRY_FILE = 'module.py' -- The file name looked for inside each module
  folder.

Edge cases
----------
Any exception raised by the module's own top-level code reaches the caller
unchanged; the registry catches and records it. A missing or non-folder path
yields an empty list.

- load_module() raises ImportError: "cannot load module: {...}"

Known limitations
-----------------
- Loading executes the file before anything checks it, so only code you trust
  belongs in the modules folder.
- There is no sandbox, signature check or unloading: an old module object lives
  until it is garbage collected.

Examples
--------
Run from the repository root.

::

    import tempfile
    from pathlib import Path
    from brisartos.host import loader

    with tempfile.TemporaryDirectory() as folder:
        (Path(folder) / 'demo').mkdir()
        (Path(folder) / 'demo' / 'module.py').write_text('VALUE = 42\n')
        paths = loader.module_files(folder)
        assert [path.parent.name for path in paths] == ['demo']
        assert loader.load_module(paths[0]).VALUE == 42
"""

import importlib.util
from pathlib import Path

ENTRY_FILE = 'module.py'


def module_files(folder):
    folder = Path(folder)
    if not folder.is_dir():
        return []
    return [entry / ENTRY_FILE for entry in sorted(folder.iterdir())
            if entry.is_dir() and (entry / ENTRY_FILE).is_file()]


def load_module(path):
    path = Path(path)
    spec = importlib.util.spec_from_file_location('brisartos_module_' + path.parent.name, path)
    if spec is None or spec.loader is None:
        raise ImportError('cannot load module: ' + str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
