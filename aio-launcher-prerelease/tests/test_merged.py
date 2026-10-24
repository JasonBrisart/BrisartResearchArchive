"""
File: tests/test_merged.py

Purpose
-------
Headless test suite covering the registry, stimuli and trial building,
the dependency audit, the file-header standard, navigation, updater
configuration, obsolete-file removal, and the trust-anchor guard. TFL
protocol, timer, output, analysis, and CLI behavior are covered by
tests/test_tfl_protocol.py.

Communication / relationships
-----------------------------
- Imports config/registries.py, frameworks/TFL/ headless modules,
  services/trust_anchor.py, and the non-GUI updater modules.
- Never imports Tkinter page modules, so it runs without a display.

Settings / parameters
---------------------
- APPDATA is redirected to a temporary folder before any project
  import, so tests never touch real settings or output folders.
- STANDARD_HEADER_SECTIONS lists the six required header sections in
  order.

Edge cases
----------
- The header test parses every .py file with ast, so a syntax error in
  any file fails the suite.
- The updater tests never make network requests.

Known limitations
-----------------
- No GUI rendering coverage.
- tests/ has no __init__.py, so run this file directly rather than with
  python -m unittest tests.test_merged.

Examples
--------
- python tests/test_merged.py
"""

from __future__ import annotations
import importlib
import pkgutil
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import os
# Force a throwaway APPDATA so tests never touch the user's real settings
# or output folders.
_TEMP_APPDATA = tempfile.mkdtemp(prefix="brisart_test_appdata_")
os.environ["APPDATA"] = _TEMP_APPDATA
from config.registries import get_available_frameworks, refresh_framework_registry
from frameworks.TFL import framework
from frameworks.TFL.config import get_default_config
from frameworks.TFL.trial_builder import build_trials


class RegistryTests(unittest.TestCase):
    def test_registry_loads_tfl(self):
        registry = refresh_framework_registry()
        self.assertTrue(any(item["id"] == "TFL" for item in registry))
        self.assertEqual(get_available_frameworks()[0]["id"], "TFL")

    def test_metadata_points_at_merged_session(self):
        self.assertEqual(framework.FRAMEWORK_METADATA["id"], "TFL")
        self.assertEqual(framework.FRAMEWORK_METADATA["runner_module"], "frameworks.TFL.session_gui")
        self.assertEqual(framework.FRAMEWORK_METADATA["runner_class"], "TFLGuiSession")


class StimulusAndTrialTests(unittest.TestCase):
    def test_stimuli_load(self):
        stimuli = framework.load_stimuli()
        self.assertEqual(len(stimuli), 60)
        self.assertEqual(stimuli[0]["stimulus_id"], "S001")

    def test_seed_reproducibility(self):
        config = get_default_config()
        stimuli = framework.apply_stimulus_limit(framework.load_stimuli(), config)
        first = build_trials(config, stimuli)
        second = build_trials(config, stimuli)
        self.assertEqual(first, second)

    def test_trial_counts(self):
        config = get_default_config()
        stimuli = framework.apply_stimulus_limit(framework.load_stimuli(), config)
        trials = build_trials(config, stimuli)
        self.assertEqual(len(trials), 120)
        self.assertEqual(sum(1 for item in trials if item["block"] == "affect"), 40)
        self.assertEqual(sum(1 for item in trials if item["block"] == "belief"), 40)
        self.assertEqual(sum(1 for item in trials if item["block"] == "contradiction"), 40)

    def test_probe_intervals(self):
        config = get_default_config()
        stimuli = framework.apply_stimulus_limit(framework.load_stimuli(), config)
        trials = build_trials(config, stimuli)
        probe_trials = [item["trial_id"] for item in trials if item["probe_trial"]]
        self.assertEqual(probe_trials[:5], [4, 8, 12, 16, 20])

    def test_delayed_reentry(self):
        config = get_default_config()
        stimuli = framework.apply_stimulus_limit(framework.load_stimuli(), config)
        trials = build_trials(config, stimuli)
        trial = trials[11]
        self.assertTrue(trial["delayed_reentry"])
        self.assertEqual(trial["recurrence_source_trial"], 6)
        source = trials[5]
        self.assertEqual(trial["stimulus_id"], source["stimulus_id"])

    def test_perturbations_when_enabled(self):
        config = get_default_config()
        config["enable_perturbations"] = True
        stimuli = framework.apply_stimulus_limit(framework.load_stimuli(), config)
        trials = build_trials(config, stimuli)
        perturbation_trials = [item["trial_id"] for item in trials if item["perturbation_trial"]]
        self.assertEqual(perturbation_trials[:4], [5, 10, 15, 20])

    def test_feedback_levels_valid(self):
        config = get_default_config()
        stimuli = framework.apply_stimulus_limit(framework.load_stimuli(), config)
        trials = build_trials(config, stimuli)
        contradiction_levels = {item["feedback_level"] for item in trials if item["block"] == "contradiction"}
        self.assertTrue(contradiction_levels.issubset({"confirmatory", "mildly_contradictory", "strongly_contradictory"}))
        self.assertEqual({item["feedback_level"] for item in trials if item["block"] == "affect"}, {"neutral"})
        self.assertEqual({item["feedback_level"] for item in trials if item["block"] == "belief"}, {"confirmatory"})
















class DependencyAuditTests(unittest.TestCase):
    def test_engine_and_analysis_layers_are_stdlib_or_internal(self):
        """
        Confirms the headless-safe layers (engine, config, frameworks)
        never import Tkinter. gui/ and frameworks/TFL/screen.py|session_gui.py
        are intentionally excluded - those are the presentation layer.
        """
        excluded_suffixes = ("screen", "session_gui")
        for package_name in ("engine", "config", "frameworks"):
            package_root = ROOT / package_name
            for module_info in pkgutil.walk_packages([str(package_root)], prefix=package_name + "."):
                name = module_info.name
                if any(name.endswith(suffix) for suffix in excluded_suffixes):
                    continue
                if name.startswith("config.state"):
                    continue  # config.state legitimately wraps Tk variables
                module = importlib.import_module(name)
                self.assertTrue(module.__name__.startswith(package_name))


STANDARD_HEADER_SECTIONS = (
    "Purpose",
    "Communication / relationships",
    "Settings / parameters",
    "Edge cases",
    "Known limitations",
    "Examples",
)


class HeaderStandardTests(unittest.TestCase):
    """
    Enforces the archive-wide file header standard: every Python file
    starts with a module docstring whose first line is "File: <path>"
    followed by the six standard sections, in order. Parsing every file
    also means any syntax error anywhere in the project fails the suite.
    """

    def _python_files(self):
        return sorted(
            path for path in ROOT.rglob("*.py")
            if "__pycache__" not in path.parts
            and "PROJECT_CONTEXT_EXPORTS" not in path.parts
        )

    def test_every_python_file_has_the_standard_header(self):
        import ast

        for path in self._python_files():
            relative = path.relative_to(ROOT).as_posix()
            with self.subTest(file=relative):
                source = path.read_text(encoding="utf-8")
                docstring = ast.get_docstring(ast.parse(source), clean=False) or ""
                lines = [line.strip() for line in docstring.strip().splitlines()]
                self.assertTrue(lines, "missing module docstring")
                self.assertEqual(lines[0], f"File: {relative}")
                positions = []
                for section in STANDARD_HEADER_SECTIONS:
                    self.assertIn(section, lines, f"missing section {section}")
                    position = lines.index(section)
                    positions.append(position)
                    self.assertGreater(position, 0, "section must follow the file line")
                    self.assertEqual(lines[position - 1], "", "missing blank line before section")
                    self.assertLess(position + 2, len(lines), "section has no body")
                    self.assertEqual(lines[position + 1], "-" * len(section), "incorrect section underline")
                    self.assertTrue(lines[position + 2], "section body must not be empty")
                self.assertEqual(positions, sorted(positions), "sections out of order")


class NavigationTests(unittest.TestCase):
    def test_sidebar_has_no_tooling_entry(self):
        from config.registries import NAV_ITEMS, SETTINGS_NAV_ITEM

        names = [name for name, _icon in NAV_ITEMS] + [SETTINGS_NAV_ITEM[0]]
        self.assertEqual(names, ["Dashboard", "Frameworks", "Results", "Archive", "Settings"])

    def test_removed_tooling_modules_are_absent_from_source(self):
        from services.updater.constants import OBSOLETE_RELEASE_PATHS

        for relative in OBSOLETE_RELEASE_PATHS:
            with self.subTest(path=relative):
                self.assertFalse((ROOT / relative).exists())


class UpdaterConfigurationTests(unittest.TestCase):
    def test_registry_url_passes_the_host_allowlist(self):
        from services.updater.constants import REGISTRY_PAGE_URL
        from services.updater.http_utils import validate_remote_url

        self.assertEqual(validate_remote_url(REGISTRY_PAGE_URL), REGISTRY_PAGE_URL)

    def test_placeholder_trust_anchor_is_reported_as_unconfigured(self):
        from services import trust_anchor

        self.assertEqual(trust_anchor.PUBLIC_KEY_DICT["n"], "0x0")
        self.assertFalse(trust_anchor.is_configured())

    def test_unconfigured_trust_anchor_blocks_update_before_network(self):
        from services.updater import orchestration

        def must_not_fetch():
            raise AssertionError("registry must not be contacted")

        original = orchestration.fetch_registry_entry
        orchestration.fetch_registry_entry = must_not_fetch
        try:
            result = orchestration.check_and_maybe_install(lambda _line: None, auto_install=True)
            startup = orchestration.startup_update_check(lambda _line: None)
        finally:
            orchestration.fetch_registry_entry = original
        self.assertEqual(result["status"], "trust_anchor_unconfigured")
        self.assertEqual(startup["status"], "trust_anchor_unconfigured")

    def test_configured_trust_anchor_is_accepted(self):
        from services import rsa_signing, trust_anchor

        public_key, _private_key = rsa_signing.generate_keypair(bits=2048)
        original = dict(trust_anchor.PUBLIC_KEY_DICT)
        trust_anchor.PUBLIC_KEY_DICT.update(rsa_signing.public_key_to_dict(public_key))
        try:
            self.assertTrue(trust_anchor.is_configured())
        finally:
            trust_anchor.PUBLIC_KEY_DICT.clear()
            trust_anchor.PUBLIC_KEY_DICT.update(original)


class ObsoleteFileRemovalTests(unittest.TestCase):
    def test_listed_files_are_removed_and_others_kept(self):
        from services.updater.install import remove_obsolete_files

        with tempfile.TemporaryDirectory() as directory:
            app_dir = Path(directory)
            (app_dir / "config").mkdir()
            obsolete = app_dir / "config" / "tooling_state.py"
            kept = app_dir / "config" / "runtime.py"
            obsolete.write_text("old", encoding="utf-8")
            kept.write_text("keep", encoding="utf-8")
            removed = remove_obsolete_files(app_dir, ("config/tooling_state.py", "gui/pages/missing.py"))
            self.assertEqual(removed, [obsolete.resolve()])
            self.assertFalse(obsolete.exists())
            self.assertTrue(kept.exists())

    def test_unsafe_entries_are_never_deleted(self):
        from services.updater.install import remove_obsolete_files

        with tempfile.TemporaryDirectory() as outer:
            outside = Path(outer) / "outside.py"
            outside.write_text("do not delete", encoding="utf-8")
            app_dir = Path(outer) / "app"
            (app_dir / "folder").mkdir(parents=True)
            removed = remove_obsolete_files(
                app_dir,
                ("../outside.py", str(outside), "folder", "C:/Windows/win.ini"),
            )
            self.assertEqual(removed, [])
            self.assertTrue(outside.exists())
            self.assertTrue((app_dir / "folder").is_dir())


if __name__ == "__main__":
    unittest.main()

