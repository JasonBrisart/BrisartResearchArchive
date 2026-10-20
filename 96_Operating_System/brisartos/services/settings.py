r"""
File: brisartos/services/settings.py

Purpose
-------
Maintain an instance-local dictionary of settings with validated writes,
defaulted lookups, removal and shallow snapshots.

Public interface:
- class Settings -- The in-memory key/value store.
- Settings.status() -- Return online.
- Settings.set(key, value) -- Store a value under a non-empty text key.
- Settings.get(key, default=None) -- Return a value, or default when the key is
  absent; unhashable keys raise TypeError.
- Settings.delete(key) -- Remove a key and return its value.
- Settings.snapshot() -- Return a shallow copy of every setting.

Design notes:

set accepts only non-empty string keys and stores values without copying. get
delegates to dictionary lookup and delete checks membership before removing the
value. snapshot copies the mapping, not the objects inside it. All state is
held by this Settings instance; no file is read or written.

Communication / relationships
-----------------------------
Depends on (project modules):
- version (version.py)
Standard library: none.
Imported by:
- brisartos/kernel/kernel.py
Covered by tests: brisartos/services/tests/test_services.py.

Settings / parameters
---------------------
No module-level settings.

Edge cases
----------
An empty or non-text key raises ValueError; deleting an unknown key raises
KeyError; get can raise TypeError for an unhashable key.

- Settings.set() raises ValueError: "setting key required"
- Settings.delete() raises KeyError: "unknown setting: {...}"

Known limitations
-----------------
- Values live in memory only and are lost when the program ends, even when
  files are kept on disk.
- Mutable values are shared by reference, not copied.

Examples
--------
Run from the repository root.

::

    from brisartos.services.settings import Settings

    settings = Settings()
    settings.set('theme', 'plain')
    assert settings.get('theme') == 'plain'
    assert settings.snapshot() == {'theme': 'plain'}
    assert settings.delete('theme') == 'plain'
"""

from version import __version__


class Settings:
    def __init__(self):
        self.version = __version__
        self._values = {}

    def status(self):
        return 'online'

    def set(self, key, value):
        if not isinstance(key, str) or not key:
            raise ValueError('setting key required')
        self._values[key] = value

    def get(self, key, default=None):
        return self._values.get(key, default)

    def delete(self, key):
        if key not in self._values:
            raise KeyError('unknown setting: ' + str(key))
        return self._values.pop(key)

    def snapshot(self):
        return dict(self._values)
