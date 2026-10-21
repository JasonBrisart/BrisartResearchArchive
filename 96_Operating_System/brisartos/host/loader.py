r"""
File: brisartos/host/loader.py

Purpose
-------
Discover module entries, parse inert manifests and execute approved entry files
through importlib.

Public interface:
- module_files(folder) -- Return sorted immediate child module.py entries.
- load_module(path) -- Execute a Python entry into a fresh module object.
- read_manifest(path) -- Read and parse manifest.txt without executing module
  code.

Design notes:

read_manifest reads only text. The extension registry validates its contents
before calling load_module. Missing manifests use the documented legacy
declaration path; they cannot be prevalidated.

Communication / relationships
-----------------------------
Standard library: importlib, pathlib.
Imported by:
- brisartos/extensions/registry.py
Covered by tests: brisartos/host/tests/test_loader.py.

Settings / parameters
---------------------
- ENTRY_FILE = 'module.py' -- Fixed local policy used by the operations
  documented above.
- MANIFEST_FILE = 'manifest.txt' -- Fixed local policy used by the operations
  documented above.

Edge cases
----------
Invalid inputs are rejected before the documented operation; backend and
callback failures propagate unless explicitly collected.

- load_module() raises ImportError: "cannot load module: {...}"
- read_manifest() raises ValueError: "invalid or duplicate manifest field:
  {...}"
- read_manifest() raises ValueError: "missing manifest fields: {...}"
- read_manifest() raises ValueError: "manifest entry must be run"

Known limitations
-----------------
- Legacy modules still execute before declaration checks.
- Even manifest-approved Python runs as trusted code without isolation or
  signature verification.

Examples
--------
Run from the repository root.

::

    from brisartos.host.loader import module_files
    assert module_files('/nonexistent/brisartos') == []
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

MANIFEST_FILE = 'manifest.txt'

def read_manifest(path):
    manifest = Path(path).with_name(MANIFEST_FILE)
    if not manifest.is_file():
        return None
    fields = {}
    allowed = {'name', 'display_name', 'version', 'author', 'description', 'api', 'api_major', 'api_minor', 'permissions', 'entry'}
    for raw in manifest.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        key, value = key.strip(), value.strip()
        if not separator or key not in allowed or key in fields:
            raise ValueError('invalid or duplicate manifest field: ' + key)
        fields[key] = value
    if set(fields) != allowed:
        raise ValueError('missing manifest fields: ' + ', '.join(sorted(allowed - set(fields))))
    if fields['entry'] != 'run':
        raise ValueError('manifest entry must be run')
    fields['api_major'] = int(fields['api_major'])
    fields['api_minor'] = int(fields['api_minor'])
    fields['permissions'] = tuple(item.strip() for item in fields['permissions'].split(',') if item.strip())
    return fields
