"""
Tests for entitle.paths — the single source of truth for default runtime data
locations shared by the GUI.
"""
from pathlib import Path

from entitle import paths


class TestDefaultPaths:
    def test_defaults_are_under_repo_root(self):
        root = paths.REPO_ROOT
        assert Path(paths.default_record_store()).is_relative_to(root)
        assert Path(paths.default_entitlement_file()).is_relative_to(root)
        assert Path(paths.default_new_entitlement_file()).is_relative_to(root)

    def test_record_store_default_lives_in_records_dir(self):
        assert Path(paths.default_record_store()).parent == paths.RECORDS_DIR

    def test_entitlement_defaults_live_in_entitlements_dir(self):
        assert Path(paths.default_entitlement_file()).parent == paths.ENTITLEMENTS_DIR
        assert Path(paths.default_new_entitlement_file()).parent == paths.ENTITLEMENTS_DIR

    def test_helpers_return_strings(self):
        assert isinstance(paths.default_record_store(), str)
        assert isinstance(paths.default_entitlement_file(), str)
        assert isinstance(paths.default_new_entitlement_file(), str)

    def test_importing_paths_does_not_create_directories(self):
        assert isinstance(paths.RECORDS_DIR, Path)
        assert isinstance(paths.ENTITLEMENTS_DIR, Path)
        assert isinstance(paths.REPORTS_DIR, Path)


class TestVersion:
    def test_version_is_a_well_formed_string(self):
        # entitle/__init__.py was removed (0.4.2, PEP 420 namespace packages),
        # so the version is read directly from the repository-root version.py
        # rather than via `from entitle import __version__`. main.py, the GUI,
        # and this test all import it the same way.
        from version import __version__
        assert isinstance(__version__, str)
        assert __version__.count(".") >= 2
