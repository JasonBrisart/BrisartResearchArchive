r"""
File: brisartos/services/updates.py

Purpose
-------
Stage source-text candidates with optional persistent indexing without
applying, authenticating or executing them.

Public interface:
- class Updates -- A source-text holding area with optional persistence.
- Updates(storage=None, encode=None, decode=None) -- Bind optional storage and
  serialization callbacks.
- Updates.start() -- Load validated candidate text and mark online.
- Updates.stop() -- Mark offline after write-through mutations.
- Updates.status() -- Return online or offline lifecycle status.
- Updates.stage(name, source) -- Commit source text under a unique non-empty
  name.
- Updates.inspect(name) -- Return a new record with fixed false
  execution/authentication flags.
- Updates.discard(name) -- Commit removal of a known candidate.
- Updates.names() -- Return sorted candidate names.

Design notes:

Mutations write a versioned candidate mapping before publishing memory changes.
Lifecycle start validates persisted source text; stop marks the service
offline.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.storage.schema (brisartos/storage/schema.py)
- version (version.py)
Standard library: none.
Imported by:
- brisartos/kernel/composition.py
Covered by tests: brisartos/services/tests/test_services.py.

Settings / parameters
---------------------
Constructor arguments select the supplied components and policies; no
module-level configuration is defined.

Edge cases
----------
Invalid inputs are rejected before the documented operation; backend and
callback failures propagate unless explicitly collected.

- Updates.__init__() raises ValueError: "persistent updates require
  serialization callbacks"
- Updates.start() raises ValueError: "invalid persisted update candidates"
- Updates.stage() raises ValueError: "update name and source text required"
- Updates.stage() raises ValueError: "update candidate already staged: {...}"
- Updates.inspect() raises KeyError: "unknown update candidate: {...}"
- Updates.discard() raises KeyError: "unknown update candidate: {...}"

Known limitations
-----------------
- Candidates remain unauthenticated and unapplied regardless of persistence.
- Index replacement is not a cross-process transaction or a power-loss
  guarantee.

Examples
--------
Run from the repository root.

::

    from brisartos.services.updates import Updates
    u = Updates()
    u.stage('candidate', 'pass')
    assert u.inspect('candidate')['applied'] is False
"""
from version import __version__
from ..storage.schema import UPDATES_PATH, envelope, payload

class Updates:
    def __init__(self, storage=None, encode=None, decode=None):
        self.version = __version__
        self._storage, self._encode, self._decode = storage, encode, decode
        self._candidates = {}
        self._online = False
        if storage is not None and (not callable(encode) or not callable(decode)):
            raise ValueError('persistent updates require serialization callbacks')
    def start(self):
        if self._storage is not None and self._storage.exists(UPDATES_PATH):
            candidates = payload(self._decode(self._storage.read(UPDATES_PATH)), 'updates')
            if any(not isinstance(k, str) or not k or not isinstance(v, str) for k, v in candidates.items()):
                raise ValueError('invalid persisted update candidates')
            self._candidates = candidates
        self._online = True
    def stop(self):
        self._online = False
    def status(self):
        return 'online' if self._online else 'offline'
    def _commit(self, candidates):
        if self._storage is not None:
            self._storage.write(UPDATES_PATH, self._encode(envelope('updates', candidates)))
        self._candidates = candidates
    def stage(self, name, source):
        if not isinstance(name, str) or not name or not isinstance(source, str):
            raise ValueError('update name and source text required')
        if name in self._candidates:
            raise ValueError('update candidate already staged: ' + name)
        candidates = dict(self._candidates)
        candidates[name] = source
        self._commit(candidates)
    def inspect(self, name):
        if name not in self._candidates:
            raise KeyError('unknown update candidate: ' + str(name))
        return {'name': name, 'source': self._candidates[name], 'applied': False, 'authenticated': False}
    def discard(self, name):
        if name not in self._candidates:
            raise KeyError('unknown update candidate: ' + str(name))
        candidates = dict(self._candidates)
        del candidates[name]
        self._commit(candidates)
    def names(self):
        return sorted(self._candidates)
