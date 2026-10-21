r"""
File: brisartos/extensions/manifest.py

Purpose
-------
Parse and structurally validate the text of a module manifest, returning its
fields without reading files or executing anything.

Public interface:
- parse_manifest(text) -- Return the manifest as a dictionary: all ten fields,
  API versions as integers and permissions as a tuple; refuse any structural
  problem.

Design notes:

The manifest schema lives here, in the layer that owns module policy.
host/loader.py only reads the text. Parsing checks shape: exact field set, no
duplicates, the fixed entry name and integer API versions. Whether the name,
permissions or API are acceptable to this runtime is decided afterwards by the
registry, using api.py and contracts.py, and always before any module code is
imported.

Communication / relationships
-----------------------------
Standard library: none.
Imported by:
- brisartos/extensions/registry.py
Covered by tests: brisartos/extensions/tests/test_manifest.py.

Settings / parameters
---------------------
- FIELDS -- The ten required manifest field names, in the documented order.
- ENTRY = 'run' -- The only accepted entry name; a manifest declares run.

Edge cases
----------
Non-text input raises TypeError. Every other problem raises ValueError and
names the field involved where one exists.

- parse_manifest() raises TypeError: "manifest must be text"
- parse_manifest() raises ValueError: "invalid or duplicate manifest field:
  {...}"
- parse_manifest() raises ValueError: "missing manifest fields: {...}"
- parse_manifest() raises ValueError: "manifest entry must be run"
- parse_manifest() raises ValueError: "manifest {...} must be a nonnegative
  integer"

Known limitations
-----------------
- Structure only: it does not validate names, permissions or API compatibility,
  and it does not authenticate the manifest.
- Lines are key=value; there is no quoting, escaping or multi-line value.
- A manifest cannot make the module code safe to run; modules remain trusted
  Python.

Examples
--------
Run from the repository root.

::

    from brisartos.extensions.manifest import parse_manifest
    text = ('name=demo\ndisplay_name=Demo\nversion=runtime\nauthor=Test\n'
            'description=Example\napi=brisartos.module\napi_major=1\napi_minor=0\n'
            'permissions=log,storage\nentry=run\n')
    fields = parse_manifest(text)
    assert fields['api_major'] == 1 and fields['permissions'] == ('log', 'storage')
"""
FIELDS = ('name', 'display_name', 'version', 'author', 'description', 'api',
          'api_major', 'api_minor', 'permissions', 'entry')
ENTRY = 'run'


def parse_manifest(text):
    if not isinstance(text, str):
        raise TypeError('manifest must be text')
    fields = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        key, value = key.strip(), value.strip()
        if not separator or key not in FIELDS or key in fields:
            raise ValueError('invalid or duplicate manifest field: ' + key)
        fields[key] = value
    missing = [name for name in FIELDS if name not in fields]
    if missing:
        raise ValueError('missing manifest fields: ' + ', '.join(sorted(missing)))
    if fields['entry'] != ENTRY:
        raise ValueError('manifest entry must be ' + ENTRY)
    for key in ('api_major', 'api_minor'):
        if not (fields[key].isascii() and fields[key].isdigit()):
            raise ValueError('manifest ' + key + ' must be a nonnegative integer')
        fields[key] = int(fields[key])
    fields['permissions'] = tuple(item.strip() for item in fields['permissions'].split(',') if item.strip())
    return fields
