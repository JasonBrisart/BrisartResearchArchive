r"""
File: brisartos/storage/state.py

Purpose
-------
Read and write one versioned state document through supplied storage and
serialization callbacks, so each stateful service does not repeat that logic.

Public interface:
- class StateFile -- One versioned state document at a fixed storage path.
- StateFile(storage, path, kind, encode, decode) -- Bind storage, a document
  path and kind, and the two serialization callbacks; refuse callbacks that
  cannot be called.
- StateFile.exists() -- Return True when the document file exists.
- StateFile.load() -- Return the validated payload mapping, or None when no
  document has been written.
- StateFile.save(values) -- Encode and write the payload, then return a
  detached copy decoded from the written text.
- StateFile.detach(values) -- Return a detached copy of plain data by encoding
  and decoding it, without touching storage.

Design notes:

Services own their validation and publication order; this file owns only the
document mechanics. save writes first and returns the decoded copy of what was
written, so a service publishes the same detached values a later load would
see. An encoding failure happens before any write, and a write failure raises
before the caller publishes anything.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.storage.schema (brisartos/storage/schema.py)
Standard library: none.
Imported by:
- brisartos/services/archive.py
- brisartos/services/settings.py
- brisartos/services/updates.py
Covered by tests: brisartos/storage/tests/test_state.py.

Settings / parameters
---------------------
Constructor arguments select the storage, document path, document kind and
callbacks; no module-level configuration is defined. Paths and the format
identifier come from brisartos/storage/schema.py.

Edge cases
----------
Invalid inputs are rejected before the documented operation; backend and
callback failures propagate unchanged, and nothing is caught here.

- StateFile.__init__() raises ValueError: "state files require serialization
  callbacks"

Known limitations
-----------------
- A missing document and a document that fails validation are different cases:
  load returns None for the first and raises for the second.
- No locking, cross-process transaction or power-loss guarantee: save is one
  storage write.
- The callbacks are trusted; this class does not check that they round-trip.

Examples
--------
Run from the repository root.

::

    from brisartos.host.serialization import decode_mapping, encode_mapping
    from brisartos.storage.state import StateFile
    from brisartos.storage.storage import Storage
    state = StateFile(Storage(), '/system/demo.txt', 'demo', encode_mapping, decode_mapping)
    assert state.load() is None
    assert state.save({'a': 1}) == {'a': 1}
    assert state.load() == {'a': 1}
"""
from .schema import envelope, payload


class StateFile:
    def __init__(self, storage, path, kind, encode, decode):
        if not callable(encode) or not callable(decode):
            raise ValueError('state files require serialization callbacks')
        self._storage, self.path, self.kind = storage, path, kind
        self._encode, self._decode = encode, decode

    def exists(self):
        return self._storage.exists(self.path)

    def load(self):
        if not self._storage.exists(self.path):
            return None
        return payload(self._decode(self._storage.read(self.path)), self.kind)

    def save(self, values):
        text = self._encode(envelope(self.kind, values))
        self._storage.write(self.path, text)
        return payload(self._decode(text), self.kind)

    def detach(self, values):
        return self._decode(self._encode(values))
