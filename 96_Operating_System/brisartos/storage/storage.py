r"""
File: brisartos/storage/storage.py

Purpose
-------
Normalize file paths and expose text storage, listings, snapshots and
restoration through Storage, with MemoryBackend as the default implementation.

Public interface:
- class MemoryBackend -- Files held in a dictionary, gone when the program
  ends.
- MemoryBackend.read(path) -- Return a file's text or raise FileNotFoundError.
- MemoryBackend.write(path, text) -- Create or replace a file, refusing a path
  that would be both a file and a folder.
- MemoryBackend.append(path, text) -- Append to a file, creating it if needed.
- MemoryBackend.delete(path) -- Delete a file or raise FileNotFoundError.
- MemoryBackend.exists(path) -- Return True only for an existing file.
- MemoryBackend.paths(prefix='/') -- Return the sorted paths under a folder.
- MemoryBackend.describe() -- Return {kind: memory}.
- inside(path, folders) -- Return True when path equals one of folders or lies
  below one.
- class Storage -- Path-validating file API over a backend.
- Storage(backend=None) -- Wrap a backend; a memory backend is used when none
  is given.
- Storage.normalize(path) -- Return the canonical /-path for a path, or raise
  ValueError for an invalid one.
- Storage.write(path, text) -- Create or replace a text file and return its
  canonical path.
- Storage.append(path, text) -- Append text to a file and return its canonical
  path.
- Storage.read(path) -- Return a file's text.
- Storage.delete(path) -- Delete a file.
- Storage.exists(path) -- Return True only for files.
- Storage.list_files(prefix='/') -- Return the sorted full paths of every file
  under a folder.
- Storage.snapshot(exclude=()) -- Return {path: text} for every file except
  those under the excluded folders.
- Storage.restore(snapshot, keep=()) -- Make storage match a snapshot exactly,
  leaving the kept folders untouched.
- Storage.describe() -- Return the backend description plus a file count.

Design notes:

Storage validates paths and text before delegation. MemoryBackend derives
directory structure from file prefixes and refuses file-versus-directory
conflicts. restore validates replacement entries before mutation, then deletes
obsolete files and writes replacements while leaving kept prefixes untouched.
Validation is separate from application: a backend error during application can
still leave a partial restore.

Communication / relationships
-----------------------------
Standard library: none.
Imported by:
- brisartos/kernel/kernel.py
Covered by tests: brisartos/events/tests/test_events.py,
brisartos/extensions/tests/test_api.py,
brisartos/services/tests/test_services.py,
brisartos/storage/tests/test_storage.py.

Settings / parameters
---------------------
No module-level settings. Backend selection is the constructor argument.

Edge cases
----------
Invalid paths (empty, containing a backslash or NUL, containing .. or naming no
file) raise ValueError, and text that is not a string raises TypeError.

- MemoryBackend.read() raises FileNotFoundError: "no such file: {...}"
- MemoryBackend.write() raises ValueError: "path conflicts with an existing
  file or folder: {...}"
- MemoryBackend.delete() raises FileNotFoundError: "no such file: {...}"
- Storage.normalize() raises ValueError: "invalid path"
- Storage.normalize() raises ValueError: "parent traversal is not permitted"
- Storage.normalize() raises ValueError: "a file path is required"
- Storage._text() raises TypeError: "text must be a string"
- Storage.restore() raises TypeError: "snapshot must be a dictionary"
- Storage.restore() raises TypeError: "snapshot values must be strings"
- Storage.restore() raises ValueError: "duplicate canonical path"
- Storage.restore() raises ValueError: "snapshot has a path that is both a file
  and a folder: {...}"

Known limitations
-----------------
- Text only. There is no binary file support.
- A snapshot holds a full copy of every file it covers in memory.
- restore applies its changes one file at a time. On the disk backend an
  operating-system failure part-way through, such as a full disk, can leave a
  mixture of old and new files.

Examples
--------
Run from the repository root.

::

    from brisartos.storage.storage import Storage

    store = Storage()
    assert store.write('notes/a.txt', 'one') == '/notes/a.txt'
    saved = store.snapshot()
    store.write('/notes/a.txt', 'two')
    store.restore(saved)
    assert store.read('/notes/a.txt') == 'one'
    store.write('/logs/k.log', 'history\n')
    assert store.snapshot(exclude=('/logs',)) == {'/notes/a.txt': 'one'}
"""

class MemoryBackend:
    def __init__(self):
        self._files = {}

    def _conflict(self, path):
        parts = path.split('/')
        for end in range(2, len(parts)):
            if '/'.join(parts[:end]) in self._files:
                return True
        folder = path + '/'
        return any(other.startswith(folder) for other in self._files)

    def read(self, path):
        if path not in self._files:
            raise FileNotFoundError('no such file: ' + path)
        return self._files[path]

    def write(self, path, text):
        if self._conflict(path):
            raise ValueError('path conflicts with an existing file or folder: ' + path)
        self._files[path] = text

    def append(self, path, text):
        if path in self._files:
            self._files[path] += text
        else:
            self.write(path, text)

    def delete(self, path):
        if path not in self._files:
            raise FileNotFoundError('no such file: ' + path)
        del self._files[path]

    def exists(self, path):
        return path in self._files

    def paths(self, prefix='/'):
        if prefix == '/':
            return sorted(self._files)
        folder = prefix + '/'
        return sorted(path for path in self._files if path.startswith(folder))

    def describe(self):
        return {'kind': 'memory'}


def inside(path, folders):
    return any(path == folder or path.startswith(folder + '/') for folder in folders)


class Storage:
    def __init__(self, backend=None):
        self.backend = MemoryBackend() if backend is None else backend

    @staticmethod
    def normalize(path):
        if not isinstance(path, str) or not path or '\\' in path or '\x00' in path:
            raise ValueError('invalid path')
        parts = []
        for part in path.split('/'):
            if part in ('', '.'):
                continue
            if part == '..':
                raise ValueError('parent traversal is not permitted')
            parts.append(part)
        if not parts:
            raise ValueError('a file path is required')
        return '/' + '/'.join(parts)

    @staticmethod
    def _text(text):
        if not isinstance(text, str):
            raise TypeError('text must be a string')
        return text

    def write(self, path, text):
        path = self.normalize(path)
        self.backend.write(path, self._text(text))
        return path

    def append(self, path, text):
        path = self.normalize(path)
        self.backend.append(path, self._text(text))
        return path

    def read(self, path):
        return self.backend.read(self.normalize(path))

    def delete(self, path):
        self.backend.delete(self.normalize(path))

    def exists(self, path):
        return self.backend.exists(self.normalize(path))

    def list_files(self, prefix='/'):
        return self.backend.paths('/' if prefix == '/' else self.normalize(prefix))

    def snapshot(self, exclude=()):
        skipped = [self.normalize(folder) for folder in exclude]
        return {path: self.backend.read(path) for path in self.backend.paths()
                if not inside(path, skipped)}

    def restore(self, snapshot, keep=()):
        if not isinstance(snapshot, dict):
            raise TypeError('snapshot must be a dictionary')
        kept = [self.normalize(folder) for folder in keep]
        replacement = {}
        for path, text in snapshot.items():
            canonical = self.normalize(path)
            if not isinstance(text, str):
                raise TypeError('snapshot values must be strings')
            if canonical in replacement:
                raise ValueError('duplicate canonical path')
            if not inside(canonical, kept):
                replacement[canonical] = text
        for path in replacement:
            parts = path.split('/')
            if any('/'.join(parts[:end]) in replacement for end in range(2, len(parts))):
                raise ValueError('snapshot has a path that is both a file and a folder: ' + path)
        for path in self.backend.paths():
            if path not in replacement and not inside(path, kept):
                self.backend.delete(path)
        for path, text in replacement.items():
            self.backend.write(path, text)

    def describe(self):
        info = dict(self.backend.describe())
        info['files'] = len(self.backend.paths())
        return info
