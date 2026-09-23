"""
tests/test_platform_info.py

Purpose
-------
Unit tests for BrisartOS's two `PlatformInfo` classes:
`brisartos/platform.py` and `brisartos/runtime/brisart_platform.py`. Both
describe the same conceptual "what hardware/ABI contract is this build
targeting" information, but they are two independently maintained classes
with different attribute sets today (a pre-runtime-package version and the
one `BrisartRuntime` actually consumes). These tests pin down each one's
`describe()` contract independently so a future consolidation of the two
doesn't silently drop a field either call site depends on.

Communication relationships
----------------------------
- `brisartos/runtime/brisart_platform.PlatformInfo` is the one imported and
  used live by `brisartos/runtime/runtime.BrisartRuntime` (see
  `runtime.py`'s `from brisart_platform import PlatformInfo`) and surfaced
  through `BrisartRuntime.print_system_info()` / the shell's `system`
  command. It is exercised again, in that integration context, by
  `tests/test_runtime.py`.
- `brisartos/platform.PlatformInfo` is not currently imported by
  `runtime.py`; it is tested here in isolation so its contract stays
  documented and protected even though nothing in the current call graph
  exercises it end-to-end.

Settings / parameters
----------------------
Neither `PlatformInfo` class takes constructor arguments; all fields are
fixed at construction time and returned verbatim by `describe()`.

Edge-case behavior
-------------------
- `brisartos/platform.py` is loaded via `_support.load_module_from_path()`
  under a private alias instead of a `sys.path`-based `import platform`,
  because the Python standard library already ships a module literally
  named `platform`. Adding `brisartos/` to `sys.path` and importing the
  bare name `platform` risks resolving to the wrong module depending on
  import order and interpreter caching -- see the docstring in
  `tests/_support.py` for the full rationale. This test file never imports
  the bare name `platform` for that reason.
- `describe()` on both classes must return a plain `dict` whose values are
  all strings, and repeated calls must return equal (though not
  necessarily identical) dictionaries, since callers such as
  `BrisartRuntime.print_system_info()` iterate over `sorted(info)` and
  print each value directly.
"""
import unittest

from _support import add_brisartos_runtime_to_syspath, load_module_from_path

add_brisartos_runtime_to_syspath()

from brisart_platform import PlatformInfo as RuntimePlatformInfo  # noqa: E402

_platform_module = load_module_from_path(
    "brisartos_platform_module", "brisartos/platform.py"
)
StandalonePlatformInfo = _platform_module.PlatformInfo


class RuntimeBrisartPlatformInfoTests(unittest.TestCase):
    """Covers brisartos/runtime/brisart_platform.py -- the one BrisartRuntime uses."""

    def setUp(self):
        self.platform = RuntimePlatformInfo()

    def test_describe_returns_all_expected_keys(self):
        info = self.platform.describe()
        expected_keys = {
            "os_name",
            "platform_profile",
            "boot_model",
            "cpu_model",
            "object_model",
            "module_abi",
            "dependency_policy",
            "module_policy",
            "future_hardware_policy",
        }
        self.assertEqual(set(info.keys()), expected_keys)

    def test_describe_values_are_strings(self):
        info = self.platform.describe()
        for key, value in info.items():
            self.assertIsInstance(value, str, f"{key} should be a string")

    def test_os_name_and_module_abi_have_expected_values(self):
        info = self.platform.describe()
        self.assertEqual(info["os_name"], "BrisartOS")
        self.assertEqual(info["module_abi"], "brisartos.module.v1")

    def test_dependency_policy_reflects_no_dependency_stance(self):
        info = self.platform.describe()
        self.assertEqual(info["dependency_policy"], "python-standard-library-only")

    def test_repeated_describe_calls_are_equal(self):
        self.assertEqual(self.platform.describe(), self.platform.describe())


class StandalonePlatformInfoTests(unittest.TestCase):
    """Covers brisartos/platform.py -- loaded by file path to avoid stdlib collision."""

    def setUp(self):
        self.platform = StandalonePlatformInfo()

    def test_describe_returns_all_expected_keys(self):
        info = self.platform.describe()
        expected_keys = {
            "target",
            "word_model",
            "boot_model",
            "module_abi",
            "dependency_mode",
        }
        self.assertEqual(set(info.keys()), expected_keys)

    def test_describe_values_are_strings(self):
        info = self.platform.describe()
        for key, value in info.items():
            self.assertIsInstance(value, str, f"{key} should be a string")

    def test_module_abi_matches_runtime_variant(self):
        """
        Both PlatformInfo classes advertise the same module ABI string.
        If this ever diverges, module permission/ABI checks in
        ModuleLoader (which hardcodes "brisartos.module.v1" as
        SUPPORTED_ABI) would need to be reconciled against whichever
        PlatformInfo is authoritative.
        """
        info = self.platform.describe()
        runtime_info = RuntimePlatformInfo().describe()
        self.assertEqual(info["module_abi"], runtime_info["module_abi"])


if __name__ == "__main__":
    unittest.main()
