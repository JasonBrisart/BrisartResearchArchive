"""
tests/test_system_api.py

Purpose
-------
Unit tests for `brisartos/runtime/system_api.py` (`SystemAPI`), the
unrestricted, framework-level API surface that `ModuleAPI` wraps with
permission checks. `SystemAPI` is the trust boundary between BrisartOS
core and everything else (modules, services, the shell), so these tests
focus on the two things most likely to silently regress: filesystem-path
sanitization (`safe_name`) and the fact that every write is scoped under
`module_data/<safe module name>/`.

Communication relationships
----------------------------
- `BrisartRuntime.__init__` (see `runtime.py`) constructs exactly one
  `SystemAPI` per runtime instance and hands it to both `ModuleLoader` and,
  indirectly through `ModuleAPI`, to every loaded module -- see
  `tests/test_runtime.py` and `tests/test_module_api.py` for the
  integration-level coverage of that wiring.
- `LoadedModule.run()` (in `module_loader.py`) calls `self.api.log(...)`
  directly on the raw `SystemAPI`, bypassing the permission wrapper
  entirely for its own "module started"/"module finished" bookkeeping
  logs -- this file tests `log()` itself; the bypass behavior is covered
  in `tests/test_module_loader.py`.

Settings / parameters
----------------------
- `SystemAPI(platform)`: `platform` is stored but otherwise only consulted
  by `get_platform_info()`, which returns `platform.describe()` verbatim.
- `module_data_root` / `logs_root` are **not** configurable via the
  constructor; they are always `Path.cwd() / "module_data"` and
  `Path.cwd() / "logs"` respectively, created eagerly (with side effects!)
  in `__init__`. Every test in this file therefore runs inside
  `_support.IsolatedCwd`, which chdir()s into a fresh temporary directory
  before constructing a `SystemAPI`, so no test ever creates or pollutes
  `module_data/`/`logs/` inside the real repository checkout.

Edge-case behavior
-------------------
- `new_object_id()` must return a 32-character lowercase hex string (128
  bits via `secrets.token_hex(16)`), and two consecutive calls must not
  collide.
- `safe_name()` must map any character that is not alphanumeric, `-`, `_`,
  or `.` to `_`, then strip leading/trailing `.`/`_` from the result, and
  must return the literal string `"unnamed"` if that leaves nothing at
  all (e.g. an all-punctuation input like `"///"`).
- `write_module_text()` / `read_module_text()` must round-trip UTF-8 text
  exactly, and `read_module_text()` for a file that was never written
  must return `None` rather than raising.
- `log()` must append (not overwrite) to `logs/<safe source>.log`, so
  multiple calls with the same `source` accumulate multiple lines rather
  than clobbering each other.
"""
import unittest
from pathlib import Path

from _support import IsolatedCwd, add_brisartos_runtime_to_syspath

add_brisartos_runtime_to_syspath()

from brisart_platform import PlatformInfo  # noqa: E402
from system_api import SystemAPI  # noqa: E402


class SystemAPIObjectIdTests(unittest.TestCase):
    def test_new_object_id_is_32_char_hex(self):
        with IsolatedCwd():
            api = SystemAPI(PlatformInfo())
            object_id = api.new_object_id()
            self.assertEqual(len(object_id), 32)
            int(object_id, 16)  # raises ValueError if not valid hex

    def test_consecutive_object_ids_do_not_collide(self):
        with IsolatedCwd():
            api = SystemAPI(PlatformInfo())
            ids = {api.new_object_id() for _ in range(50)}
            self.assertEqual(len(ids), 50)


class SystemAPISafeNameTests(unittest.TestCase):
    def setUp(self):
        self._cwd_ctx = IsolatedCwd()
        self._cwd_ctx.__enter__()
        self.api = SystemAPI(PlatformInfo())

    def tearDown(self):
        self._cwd_ctx.__exit__(None, None, None)

    def test_alnum_dash_underscore_dot_are_preserved(self):
        self.assertEqual(self.api.safe_name("Hello-World_1.2"), "Hello-World_1.2")

    def test_path_separators_become_underscores(self):
        self.assertEqual(self.api.safe_name("a/b\\c"), "a_b_c")

    def test_leading_and_trailing_dots_and_underscores_are_stripped(self):
        self.assertEqual(self.api.safe_name("..hidden.."), "hidden")

    def test_all_punctuation_input_becomes_unnamed(self):
        self.assertEqual(self.api.safe_name("///"), "unnamed")

    def test_empty_string_becomes_unnamed(self):
        self.assertEqual(self.api.safe_name(""), "unnamed")

    def test_path_traversal_attempt_is_neutralized(self):
        result = self.api.safe_name("../../etc/passwd")
        self.assertNotIn("/", result)
        self.assertNotIn("..", result.split("_"))


class SystemAPIModuleDataTests(unittest.TestCase):
    def test_write_then_read_round_trips(self):
        with IsolatedCwd():
            api = SystemAPI(PlatformInfo())
            api.write_module_text("hello_lab", "notes.txt", "hello world")
            result = api.read_module_text("hello_lab", "notes.txt")
            self.assertEqual(result, "hello world")

    def test_read_nonexistent_file_returns_none(self):
        with IsolatedCwd():
            api = SystemAPI(PlatformInfo())
            result = api.read_module_text("hello_lab", "never_written.txt")
            self.assertIsNone(result)

    def test_module_data_path_creates_directory_under_cwd(self):
        with IsolatedCwd() as tmp_dir:
            api = SystemAPI(PlatformInfo())
            path = api.module_data_path("hello_lab")
            self.assertTrue(path.exists())
            self.assertTrue(path.is_dir())
            self.assertEqual(path, Path(tmp_dir) / "module_data" / "hello_lab")

    def test_unsafe_module_name_is_sanitized_in_path(self):
        with IsolatedCwd():
            api = SystemAPI(PlatformInfo())
            path = api.write_module_text("../evil", "x.txt", "y")
            self.assertIn("module_data", path.parts)
            # The sanitized module directory must not literally be "..".
            module_data_index = path.parts.index("module_data")
            self.assertNotEqual(path.parts[module_data_index + 1], "..")


class SystemAPILogTests(unittest.TestCase):
    def test_log_appends_message_with_source_prefix(self):
        with IsolatedCwd() as tmp_dir:
            api = SystemAPI(PlatformInfo())
            api.log("hello_lab", "module started")
            log_file = Path(tmp_dir) / "logs" / "hello_lab.log"
            self.assertTrue(log_file.exists())
            content = log_file.read_text(encoding="utf-8")
            self.assertIn("hello_lab: module started", content)

    def test_multiple_log_calls_accumulate_lines(self):
        with IsolatedCwd() as tmp_dir:
            api = SystemAPI(PlatformInfo())
            api.log("hello_lab", "first")
            api.log("hello_lab", "second")
            log_file = Path(tmp_dir) / "logs" / "hello_lab.log"
            lines = log_file.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertIn("first", lines[0])
            self.assertIn("second", lines[1])


class SystemAPIPlatformInfoTests(unittest.TestCase):
    def test_get_platform_info_delegates_to_platform_describe(self):
        with IsolatedCwd():
            platform = PlatformInfo()
            api = SystemAPI(platform)
            self.assertEqual(api.get_platform_info(), platform.describe())


if __name__ == "__main__":
    unittest.main()
