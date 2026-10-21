r"""
File: brisartos/host/loader.py

Purpose
-------
Discover module entries, read the raw text of an optional manifest and execute
approved entry files through importlib.

Public interface:
- module_files(folder) -- Return sorted immediate child module.py entries.
- load_module(path) -- Execute a Python entry into a fresh module object.
- read_manifest_text(path) -- Return the text of the manifest.txt beside an
  entry file, or None when there is none; nothing is parsed or executed.

Design notes:

This adapter touches the filesystem and the import system and applies no module
policy. read_manifest_text returns text exactly as stored;
brisartos/extensions/manifest.py parses it and the registry validates it before
load_module is ever called. A missing manifest selects the documented legacy
declaration path, which cannot be validated before execution.

Communication / relationships
-----------------------------
Standard library: importlib, pathlib.
Imported by:
- brisartos/extensions/registry.py
Covered by tests: brisartos/host/tests/test_loader.py.

Settings / parameters
---------------------
- ENTRY_FILE = 'module.py' -- The entry file name looked for in each module
  folder.
- MANIFEST_FILE = 'manifest.txt' -- The manifest file name looked for beside an
  entry file.

Edge cases
----------
A missing folder yields no entries. A manifest that is not valid UTF-8 raises
UnicodeDecodeError to the caller.

- load_module() raises ImportError: "cannot load module: {...}"

Known limitations
-----------------
- Legacy modules still execute before their declarations can be checked.
- Even manifest-approved Python runs as trusted code without isolation or
  signature verification.
- The manifest text is not size-limited.

Examples
--------
Run from the repository root.

::

    from brisartos.host.loader import module_files, read_manifest_text
    assert module_files('/nonexistent/brisartos') == []
    assert read_manifest_text('/nonexistent/brisartos/module.py') is None
"""
import importlib.util
from pathlib import Path

ENTRY_FILE = 'module.py'
MANIFEST_FILE = 'manifest.txt'


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


def read_manifest_text(path):
    manifest = Path(path).with_name(MANIFEST_FILE)
    if not manifest.is_file():
        return None
    return manifest.read_text(encoding='utf-8')
