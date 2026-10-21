# Text Storage

`storage.py` defines the path policy and file API every BrisartOS component uses, together with the in-memory backend.

It imports nothing, which is why it sits at layer 0: the kernel, services and module API can all depend on it. The disk backend is not here. It lives in [`../host/disk.py`](../host/README.md), because only `host/` may touch the real filesystem; the kernel passes it in when a data folder is chosen.

## `Storage`: the path policy and the API

`Storage(backend=None)` delegates to the backend it is given, or creates a `MemoryBackend`. The public operations are `write`, `append`, `read`, `delete`, `exists`, `list_files`, `snapshot`, `restore` and `describe`.

`normalize()` removes empty and `.` components and returns one leading slash. It rejects non-text or empty input, backslashes, NUL, `..` and paths with no file component. Writes and appends require string content.

## `MemoryBackend`: files in a dictionary

`MemoryBackend` keeps text in a dictionary. Directory structure is implicit in path prefixes, and a file cannot simultaneously be a directory prefix. Listings are sorted. Missing reads and deletions raise `FileNotFoundError`.

`Storage.snapshot(exclude=())` returns file contents outside excluded prefixes. `restore(snapshot, keep=())` validates the mapping, text values, canonical duplicates and file/directory conflicts before changing files. It ignores replacement entries inside kept prefixes, deletes obsolete unprotected files and writes replacements. Backend failures during that last phase can leave a partial result.

```python
from brisartos.storage.storage import Storage

store = Storage()
store.write("notes/a.txt", "first")
saved = store.snapshot()
store.write("/notes/a.txt", "second")
store.write("/extra.txt", "temporary")
store.restore(saved)
assert store.snapshot() == {"/notes/a.txt": "first"}
```

A backend is any object with `read`, `write`, `append`, `delete`, `exists`, `paths` and `describe`. `Storage` performs no backend type check; a missing method fails when it is first called.

## Contract tests

`tests/test_storage.py` defines one contract class and runs it twice, against `MemoryBackend` and against the host disk backend in a temporary folder. It covers round trips, exact text, appends, listings, file-versus-folder conflicts, snapshots, protected prefixes, rejected restores and path validation. Concurrency, very large files and non-UTF-8 content are not covered.

## `schema.py`: stored-data ownership

The release string remains in root version.py; `schema.py` independently owns `brisartos.data.v1`, the marker `/system/state/format.txt`, settings/archive/update index paths, and envelope validation. Startup adds a missing marker without rewriting user files and refuses unknown markers. There is no automatic incompatible-format migration.

Service state lives under `/system`. Archive snapshots exclude and preserve that prefix plus `/logs`, avoiding recursive index snapshots. This convention does not prevent trusted general storage callers from editing those paths. Corrupt service documents fail startup rather than being silently discarded.
