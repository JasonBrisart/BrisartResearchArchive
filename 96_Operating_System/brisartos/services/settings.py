r"""
File: brisartos/services/settings.py

Purpose
-------
Maintain settings with optional versioned persistence, explicit service
lifecycle and write-through commits.

Public interface:
- class Settings -- A settings service with optional persistent storage.
- Settings(storage=None, encode=None, decode=None) -- Bind optional storage and
  encode/decode callbacks.
- Settings.start() -- Load and validate persisted values, then mark online.
- Settings.stop() -- Mark offline; mutations have already been written through.
- Settings.status() -- Return online or offline lifecycle status.
- Settings.set(key, value) -- Validate a key and commit a replacement value.
- Settings.get(key, default=None) -- Return a value or default; persistent
  values are detached.
- Settings.delete(key) -- Commit removal and return the previous value.
- Settings.snapshot() -- Return a detached persistent mapping or shallow memory
  copy.

Design notes:

Standalone construction remains memory-only. Composed runtimes inject storage
and serialization; a successful mutation writes before publishing memory state.
Persistent reads return detached JSON values.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.storage.schema (brisartos/storage/schema.py)
- version (version.py)
Standard library: none.
Imported by:
- brisartos/kernel/composition.py
Covered by tests: brisartos/kernel/tests/test_architecture.py,
brisartos/services/tests/test_services.py.

Settings / parameters
---------------------
Constructor arguments select the supplied components and policies; no
module-level configuration is defined.

Edge cases
----------
Invalid inputs are rejected before the documented operation; backend and
callback failures propagate unless explicitly collected.

- Settings.__init__() raises ValueError: "persistent settings require
  serialization callbacks"
- Settings.start() raises ValueError: "invalid persisted setting key"
- Settings.set() raises ValueError: "setting key required"
- Settings.delete() raises KeyError: "unknown setting: {...}"

Known limitations
-----------------
- Standalone memory mode retains shallow reference semantics.
- Persistent values must be JSON-compatible; no cross-process locking or
  multi-file transaction exists.

Examples
--------
Run from the repository root.

::

    from brisartos.services.settings import Settings
    s = Settings()
    s.start()
    s.set('theme', 'plain')
    assert s.get('theme') == 'plain'
    s.stop()
"""
from version import __version__
from ..storage.schema import SETTINGS_PATH, envelope, payload

class Settings:
    def __init__(self, storage=None, encode=None, decode=None):
        self.version = __version__
        self._storage, self._encode, self._decode = storage, encode, decode
        self._values = {}
        self._online = False
        if storage is not None and (not callable(encode) or not callable(decode)):
            raise ValueError('persistent settings require serialization callbacks')
    def start(self):
        if self._storage is not None and self._storage.exists(SETTINGS_PATH):
            values = payload(self._decode(self._storage.read(SETTINGS_PATH)), 'settings')
            if any(not isinstance(key, str) or not key for key in values):
                raise ValueError('invalid persisted setting key')
            self._values = values
        self._online = True
    def stop(self):
        self._online = False
    def status(self):
        return 'online' if self._online else 'offline'
    def _commit(self, values):
        if self._storage is not None:
            text = self._encode(envelope('settings', values))
            self._storage.write(SETTINGS_PATH, text)
            values = payload(self._decode(text), 'settings')
        self._values = values
    def set(self, key, value):
        if not isinstance(key, str) or not key:
            raise ValueError('setting key required')
        values = dict(self._values)
        values[key] = value
        self._commit(values)
    def get(self, key, default=None):
        value = self._values.get(key, default)
        if self._storage is not None and key in self._values:
            return self._decode(self._encode({'value': value}))['value']
        return value
    def delete(self, key):
        if key not in self._values:
            raise KeyError('unknown setting: ' + str(key))
        values = dict(self._values)
        value = values.pop(key)
        self._commit(values)
        return value
    def snapshot(self):
        if self._storage is not None:
            return self._decode(self._encode(self._values))
        return dict(self._values)
