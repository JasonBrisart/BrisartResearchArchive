r"""
File: brisartos/storage/schema.py

Purpose
-------
Own the stored-data format identifier, reserved state paths and versioned state
envelopes independently of release version.

Public interface:
- initialize(storage) -- Create a missing format marker or reject an
  unsupported marker.
- envelope(kind, payload) -- Wrap a mapping in a format and document-kind
  envelope.
- payload(document, kind) -- Validate the envelope and return its mapping
  payload.

Design notes:

Existing text-only trees receive a format marker without rewriting user files.
Unknown markers and incompatible envelopes are refused; no implicit migration
occurs.

Communication / relationships
-----------------------------
Standard library: none.
Imported by:
- brisartos/events/events.py
- brisartos/extensions/api.py
- brisartos/kernel/kernel.py
- brisartos/services/archive.py
- brisartos/services/settings.py
- brisartos/services/updates.py
- brisartos/storage/state.py
Covered by tests: brisartos/kernel/tests/test_architecture.py,
brisartos/services/tests/test_services.py,
brisartos/storage/tests/test_state.py.

Settings / parameters
---------------------
- DATA_FORMAT = 'brisartos.data.v1' -- Identifier of the stored-data contract,
  independent of the release version.
- FORMAT_PATH = '/system/state/format.txt' -- Marker file checked before any
  service state is loaded.
- SETTINGS_PATH = '/system/settings.txt' -- Write-through settings document.
- ARCHIVE_PATH = '/system/archive/index.txt' -- Persistent index of named
  user-file snapshots.
- UPDATES_PATH = '/system/updates/index.txt' -- Persistent index of staged
  source candidates; never an installer.
- SYSTEM_PREFIX = '/system' -- Folder holding stored-data state; archive
  snapshots exclude and preserve it.
- LOG_PREFIX = '/logs' -- Folder of per-source text logs; the one definition
  used by events and archive protection.
- MODULES_PREFIX = '/modules' -- Runtime folder under which each module's own
  files live; not the project-root modules/ source folder.
- PROTECTED_PREFIXES = (LOG_PREFIX, SYSTEM_PREFIX) -- Prefixes that archive
  snapshots exclude and archive restore preserves.

Edge cases
----------
Invalid inputs are rejected before the documented operation; backend and
callback failures propagate unless explicitly collected.

- initialize() raises ValueError: "unsupported stored-data format"
- payload() raises ValueError: "invalid or incompatible state document: {...}"
- payload() raises ValueError: "state payload must be a dictionary"

Known limitations
-----------------
- No migration between incompatible data formats is implemented.
- The /system prefix is a convention, not protection from trusted code using
  general storage.

Examples
--------
Run from the repository root.

::

    from brisartos.storage.schema import envelope, payload
    assert payload(envelope('settings', {'a': 1}), 'settings') == {'a': 1}
"""
DATA_FORMAT = 'brisartos.data.v1'
FORMAT_PATH = '/system/state/format.txt'
SETTINGS_PATH = '/system/settings.txt'
ARCHIVE_PATH = '/system/archive/index.txt'
UPDATES_PATH = '/system/updates/index.txt'
SYSTEM_PREFIX = '/system'
LOG_PREFIX = '/logs'
MODULES_PREFIX = '/modules'
PROTECTED_PREFIXES = (LOG_PREFIX, SYSTEM_PREFIX)

def initialize(storage):
    if storage.exists(FORMAT_PATH):
        if storage.read(FORMAT_PATH).strip() != DATA_FORMAT:
            raise ValueError('unsupported stored-data format')
    else:
        storage.write(FORMAT_PATH, DATA_FORMAT + '\n')

def envelope(kind, payload):
    return {'format': DATA_FORMAT, 'kind': kind, 'payload': payload}

def payload(document, kind):
    if not isinstance(document, dict) or document.get('format') != DATA_FORMAT or document.get('kind') != kind:
        raise ValueError('invalid or incompatible state document: ' + kind)
    value = document.get('payload')
    if not isinstance(value, dict):
        raise ValueError('state payload must be a dictionary')
    return value
