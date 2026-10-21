# Host Adapters

Four files provide host-backed values, disk storage, inert manifest parsing, dynamic entry-file execution and mapping serialization.

## `system.py`: values from the running process

`command_line_arguments()` returns `sys.argv[1:]`. `now_utc()` returns an aware UTC timestamp using `isoformat()`. `new_id()` returns hexadecimal text for sixteen random bytes, producing 32 characters.

These functions do not cache values, repair a wrong clock or establish identifier uniqueness. They expose the host facilities they call.

## `disk.py`: text below one root

`DiskBackend(root)` resolves the root and creates it if needed. Every target is resolved and must remain strictly below that root; a path resolving outside it, including through a symlink, raises `ValueError`.

| Method | Local behavior |
| --- | --- |
| `read(path)` | Read UTF-8 text without newline translation; missing files raise `FileNotFoundError` |
| `write(path, text)` | Create parent directories, write a sibling temporary file, then replace the destination |
| `append(path, text)` | Append directly, creating the file and parent directories when needed |
| `delete(path)` | Remove a file and prune newly empty parent directories up to the root |
| `exists(path)` | Test whether the resolved target is a file |
| `paths(prefix="/")` | Return sorted relative slash-paths under a directory |
| `describe()` | Return the disk kind and resolved root |

A file cannot also be a directory prefix. Listings omit any filename ending in `TEMP_SUFFIX`, whose value is `.brisart-tmp`. The backend expects normalized paths from its caller; it does not provide the complete public path-validation policy itself.

```python
import tempfile
from brisartos.host.disk import DiskBackend

with tempfile.TemporaryDirectory() as folder:
    disk = DiskBackend(folder)
    disk.write("/notes/a.txt", "one\r\ntwo")
    disk.append("/notes/a.txt", "!")
    assert disk.read("/notes/a.txt") == "one\r\ntwo!"
    assert disk.paths("/notes") == ["/notes/a.txt"]
```

Replacement is not a power-loss durability guarantee. There is no explicit flush-to-disk operation, no lock and no transaction spanning multiple files. The predictable temporary filename is not a secure temporary-file facility. Concurrent callers can conflict, and operating-system errors propagate.

## `loader.py`: finding and executing entries

`module_files(folder)` returns immediate child `NAME/module.py` paths in sorted order. Missing or non-directory roots produce an empty list; loose files and child directories without the entry file are ignored.

`load_module(path)` builds a fresh module object and executes the file. It does not explicitly insert that object into `sys.modules`. Top-level exceptions propagate. It checks neither module declarations nor permissions, and it does not contain untrusted code.

## Tests beside the adapters

- `tests/test_system.py`: timestamp format, identifier samples and argument types.
- `tests/test_disk.py`: exact text, temporary-file filtering, append, listings, deletion, conflicts and root escape. Symlink checks skip when creation is unavailable.
- `tests/test_loader.py`: discovery filtering, execution, fresh objects and propagated exceptions.

These tests do not simulate power failure, concurrent writers or exhausted storage.

## `serialization.py`: injected state encoding

`encode_mapping()` produces deterministic JSON for plain mappings with text keys. Unsupported values and non-finite numbers are rejected. `decode_mapping()` rejects non-mapping roots and non-finite constants. Neither operation authenticates data or enforces a size/nesting budget. Composition injects these callbacks into services.

`loader.py` additionally provides `read_manifest(path)`, reading sibling manifest.txt without execution. It rejects duplicate/unknown/missing fields, converts API versions to integers and parses comma-separated permissions. Registry performs compatibility/name/permission checks before load_module. A missing manifest selects the documented legacy path.
