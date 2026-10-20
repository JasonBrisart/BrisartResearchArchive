r"""
File: brisartos/services/archive.py

Purpose
-------
Save named in-memory snapshots through a supplied storage object and restore
them while excluding the protected log prefix.

Public interface:
- class Archive -- Named snapshots of the files in a storage object.
- Archive(storage) -- Bind the storage object that snapshots are taken from and
  restored to.
- Archive.status() -- Return online.
- Archive.save(name) -- Copy every file outside the protected folders under a
  name.
- Archive.restore(name) -- Make storage match a saved snapshot, deleting files
  that did not exist then.
- Archive.names() -- Return the sorted snapshot names.

Design notes:

The constructor receives storage instead of importing an implementation. save
replaces an existing snapshot with the same name; restore delegates to storage
with PROTECTED as the keep list. Snapshot names are non-empty strings, not
filesystem paths. The snapshots belong to this Archive instance and are never
serialized by this file.

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
- PROTECTED = ('/logs',) -- Folders the archive neither saves nor restores.

Edge cases
----------
An empty or non-text snapshot name raises ValueError; restoring an unknown name
raises KeyError; errors from storage during a restore pass through.

- Archive.save() raises ValueError: "snapshot name required"
- Archive.restore() raises KeyError: "unknown snapshot: {...}"

Known limitations
-----------------
- Snapshots live in memory only and are lost when the program ends.
- Each snapshot is a full copy of every file it covers, so many snapshots of a
  large data folder multiply memory use.

Examples
--------
Run from the repository root.

::

    from brisartos.storage.storage import Storage
    from brisartos.services.archive import Archive

    store = Storage()
    archive = Archive(store)
    store.write('/a', 'one')
    store.append('/logs/k.log', 'kept\n')
    archive.save('first')
    store.write('/a', 'two')
    archive.restore('first')
    assert store.read('/a') == 'one'
    assert store.read('/logs/k.log') == 'kept\n'
"""

from version import __version__

PROTECTED = ('/logs',)


class Archive:
    def __init__(self, storage):
        self.version = __version__
        self._storage = storage
        self._snapshots = {}

    def status(self):
        return 'online'

    def save(self, name):
        if not isinstance(name, str) or not name:
            raise ValueError('snapshot name required')
        self._snapshots[name] = self._storage.snapshot(exclude=PROTECTED)

    def restore(self, name):
        if name not in self._snapshots:
            raise KeyError('unknown snapshot: ' + str(name))
        self._storage.restore(self._snapshots[name], keep=PROTECTED)

    def names(self):
        return sorted(self._snapshots)
