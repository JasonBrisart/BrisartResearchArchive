"""
tests/test_filesystem_service.py

Purpose
-------
Unit tests for `brisartos/services/filesystem_service.py`
(`FilesystemService`, `FilesystemAccessError`). This is BrisartOS's one
service with real, security-relevant behavior today: it is the only
built-in service a module can use to persist arbitrary data, and its
entire safety model rests on `safe_name()` collapsing any filename a
module supplies into something that can never resolve outside that
module's own `module_data/<module_name>/` directory. These tests both
confirm the happy-path CRUD contract and actively probe the sandbox with
path-traversal-style filenames.

Communication relationships
----------------------------
- `ServiceRegistry.register_builtin_services()` (see
  `tests/test_service_registry.py`) constructs the one `FilesystemService`
  instance a `BrisartRuntime` ever registers, passing it
  `SystemAPI.module_data_root` so both `SystemAPI.write_module_text()` and
  `FilesystemService.write_text()` end up writing under the same
  `module_data/` tree in practice, even though the two implement their own
  independent sanitization logic.
- `modules/hello_lab/module.py` is the one shipped module that actually
  calls this service (`api.get_service("filesystem")` then
  `fs.write_text(...)` / `fs.list_files(...)`), gated behind the
  `"service:filesystem"` permission tested in `tests/test_module_api.py`.
  `tests/test_hello_lab_module.py` exercises that exact call path
  end-to-end.

Settings / parameters
----------------------
- `FilesystemService(module_data_root=None)`: unlike `SystemAPI`, this
  service's data root **is** constructor-configurable, which is what makes
  it possible to point every test in this file at a fresh `tempfile`
  directory instead of `Path.cwd()`. When `module_data_root` is falsy, it
  falls back to the literal relative path `"module_data"` under the
  current working directory -- see the isolation note in
  `tests/test_service_registry.py`'s docstring for why that fallback path
  is exercised inside `IsolatedCwd` rather than directly here.
- Every public method (`list_files`, `exists`, `read_text`, `write_text`,
  `read_bytes`, `write_bytes`, `delete_file`, `file_info`) takes
  `(module_name, filename, ...)`; both are passed through `safe_name()`
  before touching disk.

Edge-case behavior
-------------------
- `safe_name()` maps any character outside `[A-Za-z0-9._-]` to `_`, then
  strips leading/trailing `.`/`_`. Because `/` and `\\` are among the
  characters replaced, a `filename` such as `"../../etc/passwd"` can never
  actually produce a path with more than one component -- so the explicit
  `FilesystemAccessError` containment check in `_resolve()` is a
  defense-in-depth measure that current inputs cannot trigger through the
  public API alone. This file tests both halves of that story explicitly:
  that traversal-style filenames are neutralized into a safe, single-level
  filename, and that `_resolve()`'s containment check holds even when
  exercised directly.
- `read_text()` / `read_bytes()` / `file_info()` must return `None` (not
  raise) for a file that does not exist; `delete_file()` must return
  `False` (not raise) for a file that does not exist and `True` when it
  successfully removes one.
- `list_files()` must return only files (never subdirectories) in sorted
  order, scoped to the one module's own directory.
"""
import tempfile
import unittest
from pathlib import Path

from _support import add_brisartos_services_to_syspath

add_brisartos_services_to_syspath()

from filesystem_service import FilesystemAccessError, FilesystemService  # noqa: E402


class FilesystemServiceTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.fs = FilesystemService(module_data_root=self.root)

    def tearDown(self):
        self._tmp.cleanup()


class FilesystemServiceTextRoundTripTests(FilesystemServiceTestCase):
    def test_write_then_read_text_round_trips(self):
        self.fs.write_text("hello_lab", "notes.txt", "hello world")
        self.assertEqual(self.fs.read_text("hello_lab", "notes.txt"), "hello world")

    def test_read_text_missing_file_returns_none(self):
        self.assertIsNone(self.fs.read_text("hello_lab", "missing.txt"))

    def test_write_bytes_then_read_bytes_round_trips(self):
        self.fs.write_bytes("hello_lab", "blob.bin", b"\x00\x01\x02\xff")
        self.assertEqual(self.fs.read_bytes("hello_lab", "blob.bin"), b"\x00\x01\x02\xff")

    def test_read_bytes_missing_file_returns_none(self):
        self.assertIsNone(self.fs.read_bytes("hello_lab", "missing.bin"))

    def test_write_creates_module_directory_under_root(self):
        self.fs.write_text("hello_lab", "notes.txt", "x")
        expected_dir = self.root / "hello_lab"
        self.assertTrue(expected_dir.is_dir())


class FilesystemServiceListingAndExistenceTests(FilesystemServiceTestCase):
    def test_exists_true_after_write_false_before(self):
        self.assertFalse(self.fs.exists("hello_lab", "a.txt"))
        self.fs.write_text("hello_lab", "a.txt", "x")
        self.assertTrue(self.fs.exists("hello_lab", "a.txt"))

    def test_list_files_returns_sorted_names(self):
        self.fs.write_text("hello_lab", "zeta.txt", "z")
        self.fs.write_text("hello_lab", "alpha.txt", "a")
        self.fs.write_text("hello_lab", "mid.txt", "m")
        self.assertEqual(
            self.fs.list_files("hello_lab"),
            ["alpha.txt", "mid.txt", "zeta.txt"],
        )

    def test_list_files_empty_module_directory(self):
        self.assertEqual(self.fs.list_files("brand_new_module"), [])

    def test_list_files_excludes_subdirectories(self):
        self.fs.write_text("hello_lab", "a.txt", "a")
        (self.root / "hello_lab" / "a_subdir").mkdir()
        self.assertEqual(self.fs.list_files("hello_lab"), ["a.txt"])

    def test_different_modules_have_isolated_directories(self):
        self.fs.write_text("module_a", "shared_name.txt", "from a")
        self.fs.write_text("module_b", "shared_name.txt", "from b")
        self.assertEqual(self.fs.read_text("module_a", "shared_name.txt"), "from a")
        self.assertEqual(self.fs.read_text("module_b", "shared_name.txt"), "from b")


class FilesystemServiceDeleteAndInfoTests(FilesystemServiceTestCase):
    def test_delete_existing_file_returns_true_and_removes_it(self):
        self.fs.write_text("hello_lab", "a.txt", "x")
        self.assertTrue(self.fs.delete_file("hello_lab", "a.txt"))
        self.assertFalse(self.fs.exists("hello_lab", "a.txt"))

    def test_delete_missing_file_returns_false(self):
        self.assertFalse(self.fs.delete_file("hello_lab", "missing.txt"))

    def test_file_info_missing_file_returns_none(self):
        self.assertIsNone(self.fs.file_info("hello_lab", "missing.txt"))

    def test_file_info_returns_name_size_and_path(self):
        self.fs.write_text("hello_lab", "a.txt", "12345")
        info = self.fs.file_info("hello_lab", "a.txt")
        self.assertEqual(info["name"], "a.txt")
        self.assertEqual(info["size_bytes"], 5)
        self.assertTrue(info["path"].endswith("a.txt"))


class FilesystemServiceSandboxingTests(FilesystemServiceTestCase):
    def test_safe_name_replaces_path_separators(self):
        self.assertEqual(self.fs.safe_name("a/b\\c"), "a_b_c")

    def test_safe_name_strips_leading_trailing_dots_and_underscores(self):
        self.assertEqual(self.fs.safe_name("..secret.."), "secret")

    def test_safe_name_empty_result_becomes_unnamed(self):
        self.assertEqual(self.fs.safe_name("///"), "unnamed")

    def test_traversal_style_filename_stays_inside_module_directory(self):
        # safe_name() collapses this into a single path component, so the
        # write can never land outside module_data/hello_lab/.
        self.fs.write_text("hello_lab", "../../etc/passwd", "gotcha")
        module_dir = self.root / "hello_lab"
        files_in_module_dir = list(module_dir.iterdir())
        self.assertEqual(len(files_in_module_dir), 1)
        self.assertTrue(
            str(files_in_module_dir[0].resolve()).startswith(str(module_dir.resolve()))
        )

    def test_traversal_style_module_name_stays_inside_root(self):
        self.fs.write_text("../../evil_module", "a.txt", "gotcha")
        # The sanitized module directory must be a direct child of root,
        # never root's parent or an arbitrary ancestor.
        created_dirs = [entry for entry in self.root.iterdir() if entry.is_dir()]
        for entry in created_dirs:
            self.assertEqual(entry.parent.resolve(), self.root.resolve())

    def test_resolve_always_stays_within_module_directory(self):
        """
        Defense-in-depth check on the private _resolve() containment
        logic directly, independent of safe_name()'s own sanitization.
        Every filename tried here would traverse outside the module
        directory if safe_name() were ever weakened to pass slashes or
        ".." components through unchanged; _resolve()'s explicit
        `module_dir not in target.parents` check exists specifically to
        catch that scenario, so this test documents the guarantee even
        though safe_name() already makes it unreachable through the
        public API today.
        """
        module_dir = self.fs._module_dir("hello_lab")
        malicious_inputs = [".", "..", "../../etc/passwd", "/etc/passwd", ""]
        for raw_filename in malicious_inputs:
            with self.subTest(filename=raw_filename):
                target = self.fs._resolve("hello_lab", raw_filename)
                self.assertTrue(
                    target == module_dir or module_dir in target.parents,
                    f"{target} escaped {module_dir} for input {raw_filename!r}",
                )


if __name__ == "__main__":
    unittest.main()
