r"""
File: brisartos/services/archive.py

Purpose
-------
Save named user-file snapshots with optional persistent indexing while
excluding logs and system state.

Public interface:
- class Archive -- Named snapshots of user files with optional persistence.
- Archive(storage, encode=None, decode=None) -- Bind storage and optional
  paired serialization callbacks.
- Archive.start() -- Load the snapshot index and mark online.
- Archive.stop() -- Mark offline after write-through operations.
- Archive.status() -- Return online or offline lifecycle status.
- Archive.save(name) -- Copy user files under a name and persist the index if
  configured.
- Archive.restore(name) -- Restore a known snapshot while preserving protected
  prefixes.
- Archive.names() -- Return sorted snapshot names.

Design notes:

Snapshots exclude /logs and /system so their own persistent index is never
recursively archived. Restore preserves both prefixes and delegates
validation/application to Storage.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.storage.schema (brisartos/storage/schema.py)
- brisartos.storage.state (brisartos/storage/state.py)
- version (version.py)
Standard library: none.
Imported by:
- brisartos/kernel/composition.py
Covered by tests: brisartos/services/tests/test_services.py.

Settings / parameters
---------------------
- PROTECTED = PROTECTED_PREFIXES -- The prefixes archive snapshots exclude and
  restore preserves, defined in brisartos/storage/schema.py.

Edge cases
----------
Invalid inputs are rejected before the documented operation; backend and
callback failures propagate unless explicitly collected.

- Archive.__init__() raises ValueError: "both serialization callbacks are
  required"
- Archive.start() raises ValueError: "invalid persisted snapshot"
- Archive.start() raises ValueError: "invalid persisted snapshot file"
- Archive.save() raises ValueError: "snapshot name required"
- Archive.restore() raises KeyError: "unknown snapshot: {...}"

Known limitations
-----------------
- Snapshots are full copies; a large index consumes memory and disk.
- Restore is not transactional across files and does not roll back settings or
  update candidates.

Examples
--------
Run from the repository root.

::

    from brisartos.services.archive import Archive
    from brisartos.storage.storage import Storage
    s = Storage()
    a = Archive(s)
    s.write('/a', 'one')
    a.save('first')
    s.write('/a', 'two')
    a.restore('first')
    assert s.read('/a') == 'one'
"""
from version import __version__
from ..storage.schema import ARCHIVE_PATH, PROTECTED_PREFIXES
from ..storage.state import StateFile
PROTECTED = PROTECTED_PREFIXES


class Archive:
    def __init__(self, storage, encode=None, decode=None):
        self.version = __version__
        self._storage = storage
        if (encode is None) != (decode is None):
            raise ValueError('both serialization callbacks are required')
        self._state = None if encode is None else StateFile(storage, ARCHIVE_PATH, 'archive', encode, decode)
        self._snapshots = {}
        self._online = False

    def start(self):
        if self._state is not None:
            snapshots = self._state.load()
            if snapshots is not None:
                for name, files in snapshots.items():
                    if not isinstance(name, str) or not name or not isinstance(files, dict):
                        raise ValueError('invalid persisted snapshot')
                    for path, text in files.items():
                        if self._storage.normalize(path) != path or not isinstance(text, str):
                            raise ValueError('invalid persisted snapshot file')
                self._snapshots = snapshots
        self._online = True

    def stop(self):
        self._online = False

    def status(self):
        return 'online' if self._online else 'offline'

    def save(self, name):
        if not isinstance(name, str) or not name:
            raise ValueError('snapshot name required')
        snapshots = dict(self._snapshots)
        snapshots[name] = self._storage.snapshot(exclude=PROTECTED)
        if self._state is not None:
            snapshots = self._state.save(snapshots)
        self._snapshots = snapshots

    def restore(self, name):
        if name not in self._snapshots:
            raise KeyError('unknown snapshot: ' + str(name))
        self._storage.restore(self._snapshots[name], keep=PROTECTED)

    def names(self):
        return sorted(self._snapshots)
