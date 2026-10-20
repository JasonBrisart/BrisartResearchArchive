r"""
File: brisartos/host/disk.py

Purpose
-------
Store text files beneath a resolved root directory through DiskBackend,
including replacement writes, direct appends, recursive listings and deletion
of empty parent directories.

Public interface:
- class DiskBackend -- Files below a single resolved root folder, created on
  construction if missing.
- DiskBackend(root) -- Resolve root, create it if needed and remember it.
- DiskBackend.read(path) -- Return a file's text exactly as stored.
- DiskBackend.write(path, text) -- Create or replace a file atomically,
  creating parent folders as needed.
- DiskBackend.append(path, text) -- Append text to a file, creating it if
  needed.
- DiskBackend.delete(path) -- Delete a file, then remove any parent folders
  left empty.
- DiskBackend.exists(path) -- Return True only for an existing file, not a
  folder.
- DiskBackend.paths(prefix='/') -- Return the sorted /-paths of every file
  under prefix, or an empty list when that folder is missing.
- DiskBackend.describe() -- Return {kind: disk, root: ...}.

Design notes:

Every operation resolves its target and checks that it remains below root.
Replacement writes use a sibling temporary path followed by replace(); append
writes directly to the destination. Listings omit names ending in TEMP_SUFFIX.
This implementation has no locking or flush-to-disk step, so replacement must
not be described as a crash-durability guarantee.

Communication / relationships
-----------------------------
Standard library: pathlib.
Imported by:
- brisartos/kernel/kernel.py
Covered by tests: brisartos/host/tests/test_disk.py,
brisartos/kernel/tests/test_storage.py.

Settings / parameters
---------------------
- TEMP_SUFFIX = '.brisart-tmp' -- Suffix of the temporary file used for an
  atomic write; such files are ignored when listing.
- CONFLICT = 'path conflicts with an existing file or folder: ' -- Message
  prefix used when a path would be both a file and a folder.

Edge cases
----------
Operating-system errors such as a full disk or a missing permission are not
caught and reach the caller. delete removes folders that become empty.

- DiskBackend._target() raises ValueError: "path escapes the storage root:
  {...}"
- DiskBackend._prepare() raises ValueError: "path conflicts with an existing
  file or folder: {...}"
- DiskBackend.read() raises FileNotFoundError: "no such file: {...}"
- DiskBackend.delete() raises FileNotFoundError: "no such file: {...}"
- DiskBackend._prepare() catches (FileExistsError, NotADirectoryError) --
  Converts the operating system's file-versus-folder clash into the same
  ValueError the memory backend raises.

Known limitations
-----------------
- No locking: two programs sharing one folder can interleave appends or lose
  one of two simultaneous writes to the same file.
- Appends write directly; replacement writes use rename without a power-loss
  durability guarantee.
- paths() walks the folder on every call, so listing the whole tree gets slower
  as the number of files grows. A prefix limits the walk to that folder.
- On case-insensitive filesystems, paths that differ only by case are the same
  file. This has not been tested on case-insensitive hosts.
- This is not secure temporary-file creation or a durability guarantee: the
  temporary file is not flushed with fsync before the rename.

Examples
--------
Run from the repository root.

::

    import tempfile
    from brisartos.host.disk import DiskBackend

    with tempfile.TemporaryDirectory() as folder:
        disk = DiskBackend(folder)
        disk.write('/notes/a.txt', 'hi')
        disk.append('/notes/a.txt', '!')
        assert disk.read('/notes/a.txt') == 'hi!'
        assert disk.paths() == ['/notes/a.txt']
        assert disk.paths('/other') == []
"""

from pathlib import Path

TEMP_SUFFIX = '.brisart-tmp'
CONFLICT = 'path conflicts with an existing file or folder: '


class DiskBackend:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _target(self, path):
        target = (self.root / path.lstrip('/')).resolve()
        if target == self.root or self.root not in target.parents:
            raise ValueError('path escapes the storage root: ' + path)
        return target

    def _prepare(self, path):
        target = self._target(path)
        if target.is_dir():
            raise ValueError(CONFLICT + path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except (FileExistsError, NotADirectoryError):
            raise ValueError(CONFLICT + path) from None
        return target

    def read(self, path):
        target = self._target(path)
        if not target.is_file():
            raise FileNotFoundError('no such file: ' + path)
        with target.open('r', encoding='utf-8', newline='') as handle:
            return handle.read()

    def write(self, path, text):
        target = self._prepare(path)
        temp = target.with_name(target.name + TEMP_SUFFIX)
        with temp.open('w', encoding='utf-8', newline='') as handle:
            handle.write(text)
        temp.replace(target)

    def append(self, path, text):
        target = self._prepare(path)
        with target.open('a', encoding='utf-8', newline='') as handle:
            handle.write(text)

    def delete(self, path):
        target = self._target(path)
        if not target.is_file():
            raise FileNotFoundError('no such file: ' + path)
        target.unlink()
        parent = target.parent
        while parent != self.root and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent

    def exists(self, path):
        return self._target(path).is_file()

    def paths(self, prefix='/'):
        base = self.root if prefix == '/' else self._target(prefix)
        if not base.is_dir():
            return []
        return sorted('/' + item.relative_to(self.root).as_posix()
                      for item in base.rglob('*')
                      if item.is_file() and not item.name.endswith(TEMP_SUFFIX))

    def describe(self):
        return {'kind': 'disk', 'root': str(self.root)}
