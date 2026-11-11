"""
File: tests/test_gui.py

Purpose
-------
Verify the window's behavior without a display: the six tabs exist in order, fields shared
  between tabs really are one variable, the whole workflow (issue, verify, deploy up to and past
  the limit, fork, provenance, revoke, refused deployment, reinstate, check, report, list)
  works by pressing the real buttons with nothing retyped between tabs, a file written by the
  previous encryption is flagged on Verify and migrated by its button, errors show in the
  output pane and a dialog instead of closing the window, and no window opening is reported as
  an error.

Communication / relationships
-----------------------------
Installs tests/fake_tk.py as tkinter for one test at a time and imports the real gui/window.py
  (and through it gui/tabs.py) against it. Also imports entitle/common.py (EntitleError),
  entitle/encryption.py (to simulate a missing 97_Encryption), version.py and tests/support.py.
  Run by pytest; nothing imports it.

Settings / parameters
---------------------
The gui fixture swaps the tkinter modules in sys.modules, clears gui.* modules before and after
  so no module bound to the stand-in leaks into other tests, and yields a started window plus
  helpers: form(tab title), click(button text) and out() (the output pane text). Files are
  written under pytest's tmp_path through the shared entitlement_file and store fields.

Edge cases
----------
Covers a deployment limit that is not a whole number, a short key (error dialog and
  "ERROR: EntitleBSRError" in the pane), a wrong key on Verify (shown as a denied result, not an
  error), optional fields left empty (stored as null, not empty text), a missing 97_Encryption
  (an error, never a denial), migrating a file that does not open (an error, file untouched), a
  record store holding a corrupted line, and a Tk that cannot open a display.

Known limitations
-----------------
The stand-in does not draw or lay out anything, so appearance, spacing, focus order and real
  file dialogs need a manual check on a real display. Actions run synchronously here; a real
  window runs them on the interface thread.

Examples
--------
From the directory containing run.py:

    python -m pytest tests/test_gui.py
"""

import json
import shutil
import sys
from pathlib import Path

import pytest

import fake_tk
from entitle import encryption
from entitle.common import EntitleError
from support import DRBG_PERSONALIZATION, DRBG_SEED, LEGACY_ENTITLEMENT, MASTER_KEY
from version import __version__

TAB_TITLES = ["Issue", "Verify", "Deploy", "Fork / Provenance", "Revoke / Reinstate", "Audit Report"]


def _purge_gui_modules():
    for name in [m for m in sys.modules if m == "gui" or m.startswith("gui.")]:
        del sys.modules[name]


class Window:
    def __init__(self, module):
        fake_tk.reset()
        self.module = module
        self.app = module.EntitleApp()
        self.forms = {text: frame for frame, text in fake_tk.NOTEBOOKS[0].tabs}

    def form(self, title):
        return self.forms[title]

    def set(self, title, key, value):
        self.forms[title].vars[key].set(value)

    def click(self, text):
        buttons = fake_tk.buttons(text)
        assert len(buttons) == 1, f"expected one {text!r} button, found {len(buttons)}"
        buttons[0].invoke()

    def out(self):
        return self.app.output.text

    def data(self):
        return json.loads(self.out())


@pytest.fixture
def window(monkeypatch):
    for name, module in fake_tk.modules().items():
        monkeypatch.setitem(sys.modules, name, module)
    _purge_gui_modules()
    import gui.window

    yield Window(gui.window)
    _purge_gui_modules()


@pytest.fixture
def ready(window, tmp_path):
    window.app.shared["master_key"].set(MASTER_KEY)
    window.app.shared["entitlement_file"].set(str(tmp_path / "ent" / "lab.entitle"))
    window.app.shared["store"].set(str(tmp_path / "rec" / "r.log"))
    window.set("Issue", "entitlement_id", "gui-lab-1")
    window.set("Issue", "drbg_seed", DRBG_SEED)
    window.set("Issue", "drbg_personalization", DRBG_PERSONALIZATION)
    window.set("Issue", "deployment_limit", "5")
    return window


class TestStructure:
    def test_six_tabs_appear_in_order_and_the_title_carries_the_version(self, window):
        assert [text for _, text in fake_tk.NOTEBOOKS[0].tabs] == TAB_TITLES
        assert window.app.window_title.startswith(f"Entitle {__version__}")

    def test_fields_shared_between_tabs_are_one_variable(self, window):
        for key in ("issuer", "subject", "product", "master_key"):
            assert window.form("Issue").vars[key] is window.form("Verify").vars[key] is window.form("Deploy").vars[key]
        assert window.form("Issue").vars["entitlement_file"] is window.form("Verify").vars["entitlement_file"]
        for title in ("Deploy", "Fork / Provenance", "Revoke / Reinstate", "Audit Report"):
            assert window.form(title).vars["store"] is window.form("Deploy").vars["store"]
        assert window.form("Revoke / Reinstate").vars["issuer"] is window.form("Issue").vars["issuer"]

    def test_typing_in_one_tab_shows_in_the_others(self, window):
        window.set("Issue", "master_key", "typed-once")
        assert window.form("Deploy").get("master_key") == "typed-once"

    def test_the_demo_defaults_match_the_documented_commands(self, window):
        assert window.form("Issue").get("issuer") == "JasonBrisart"
        assert window.form("Issue").get("subject") == "ResearchLabA"
        assert window.form("Issue").get("product") == "EntitleDemo"
        assert window.form("Verify").get("entitlement_file").endswith("lab_a.entitle")
        assert window.form("Deploy").get("store").endswith("entitle_records.log")


class TestWorkflow:
    def test_the_whole_workflow_runs_with_nothing_retyped_between_tabs(self, ready):
        w = ready
        w.set("Issue", "modify", True)
        w.click("Issue Entitlement")
        issued = w.data()
        assert issued["created"].endswith("lab.entitle") and issued["payload"]["rights"]["can_modify"] is True
        w.click("Verify Entitlement")
        assert w.data()["allowed"] is True and w.data()["rights"]["deployment_limit"] == 5
        w.set("Deploy", "host", "node-1")
        w.click("Record Deployment")
        assert w.data()["recorded"] is True and w.data()["deployments_used"] == 1
        w.set("Deploy", "host", "node-2")
        w.click("Record Deployment")
        assert w.data()["deployments_used"] == 2
        for key, value in (("source_version", "1.0"), ("fork_name", "lab-custom"), ("maintainer", "Lab"),
                           ("version", "1.1"), ("custodian", "Lab"), ("previous_version", "1.0")):
            w.set("Fork / Provenance", key, value)
        w.click("Record Fork")
        assert w.data()["record_type"] == "fork" and w.data()["data"]["fork_name"] == "lab-custom"
        w.click("Record Provenance")
        assert w.data()["data"]["previous_version"] == "1.0" and w.data()["data"]["origin"] == "JasonBrisart"
        w.set("Revoke / Reinstate", "entitlement_id", "gui-lab-1")
        w.set("Revoke / Reinstate", "reason", "key compromise")
        w.click("Revoke")
        assert w.data()["record_type"] == "revocation"
        w.click("Check Status")
        assert w.data()["revoked"] is True
        w.click("Record Deployment")
        assert w.data()["reason"] == "entitlement_revoked"
        w.click("Reinstate")
        w.click("Check Status")
        assert w.data()["revoked"] is False
        w.set("Deploy", "host", "node-3")
        w.click("Record Deployment")
        assert w.data()["deployments_used"] == 3
        w.click("Generate Report")
        assert "deployment: 3" in w.out() and "VERIFIED: hash chain intact across 7 records." in w.out()
        w.click("List All Records")
        assert len(w.data()) == 7

    def test_the_deployment_limit_is_refused_in_the_pane_not_in_a_dialog(self, ready):
        ready.set("Issue", "deployment_limit", "1")
        ready.click("Issue Entitlement")
        ready.set("Deploy", "host", "a")
        ready.click("Record Deployment")
        ready.set("Deploy", "host", "b")
        ready.click("Record Deployment")
        assert ready.data()["reason"] == "deployment_limit_reached"
        assert fake_tk.MESSAGES == []

    def test_a_wrong_key_on_verify_is_a_denied_result_not_an_error(self, ready):
        ready.click("Issue Entitlement")
        ready.app.shared["master_key"].set("wrong-key-wrong-key-wrong-key-wrong-key")
        ready.click("Verify Entitlement")
        assert ready.data()["allowed"] is False and ready.data()["reason"] == "bsr_verification_failed"
        assert fake_tk.MESSAGES == []

    def test_optional_fields_left_empty_are_stored_as_null_not_empty_text(self, ready):
        for key, value in {"source_version": "1.0", "fork_name": "f", "maintainer": "m"}.items():
            ready.set("Fork / Provenance", key, value)
        ready.click("Record Fork")
        assert ready.data()["data"]["environment"] is None and ready.data()["data"]["notes"] is None
        ready.set("Revoke / Reinstate", "entitlement_id", "gui-lab-1")
        ready.click("Revoke")
        assert ready.data()["data"]["reason"] is None

    def test_browse_fills_the_shared_field_and_cancelling_leaves_it(self, ready):
        before = ready.app.shared["entitlement_file"].get()
        fake_tk.DIALOG_FILE[0] = ""
        fake_tk.buttons("Browse…")[0].invoke()
        assert ready.app.shared["entitlement_file"].get() == before
        fake_tk.DIALOG_FILE[0] = "/chosen/path.entitle"
        for button in fake_tk.buttons("Browse…"):
            if button.master is ready.form("Verify"):
                button.invoke()
        assert ready.app.shared["entitlement_file"].get() == "/chosen/path.entitle"


class TestMigrate:
    def test_a_previous_encryption_file_is_flagged_on_verify_and_migrated_by_its_button(self, ready):
        path = Path(ready.app.shared["entitlement_file"].get())
        path.parent.mkdir(parents=True)
        shutil.copyfile(LEGACY_ENTITLEMENT, path)
        ready.click("Verify Entitlement")
        assert ready.data()["allowed"] is True and "previous encryption" in ready.data()["note"]
        ready.click("Migrate to Current Encryption")
        assert ready.data() == {"migrated": True, "reason": "migrated", "entitlement_id": "lab-a-demo-001"}
        ready.click("Verify Entitlement")
        assert ready.data()["allowed"] is True and "note" not in ready.data()
        ready.click("Migrate to Current Encryption")
        assert ready.data()["reason"] == "already_current_encryption"
        assert fake_tk.MESSAGES == []

    def test_a_file_that_does_not_open_is_an_error_and_is_not_changed(self, ready):
        path = Path(ready.app.shared["entitlement_file"].get())
        path.parent.mkdir(parents=True)
        shutil.copyfile(LEGACY_ENTITLEMENT, path)
        before = path.read_bytes()
        ready.app.shared["master_key"].set("wrong-key-wrong-key-wrong-key-wrong-key")
        ready.click("Migrate to Current Encryption")
        assert ready.out().startswith("ERROR: EntitleError:") and "Nothing was changed." in ready.out()
        assert [kind for kind, _, _ in fake_tk.MESSAGES] == ["showerror"]
        assert path.read_bytes() == before

    def test_a_missing_encryption_is_an_error_not_a_denial(self, ready, monkeypatch):
        ready.click("Issue Entitlement")
        unavailable = encryption.EncryptionLink(available=False, location=encryption.ENCRYPTION_DIR, problem="gone")
        monkeypatch.setattr(encryption, "status", lambda: unavailable)
        ready.click("Verify Entitlement")
        assert ready.out() == "ERROR: EncryptionNotFoundError: Encryption not found: gone"


class TestErrors:
    def test_a_short_key_shows_the_reason_in_the_pane_and_a_dialog(self, ready):
        ready.app.shared["master_key"].set("short")
        ready.click("Issue Entitlement")
        assert ready.out() == "ERROR: EntitleBSRError: BSR2 encryption failed: master key must contain at least 32 bytes"
        assert [kind for kind, _, _ in fake_tk.MESSAGES] == ["showerror"]
        assert "master key must contain at least 32 bytes" in fake_tk.MESSAGES[0][2]

    def test_a_deployment_limit_that_is_not_a_number_is_named_in_the_message(self, ready):
        ready.set("Issue", "deployment_limit", "lots")
        ready.click("Issue Entitlement")
        assert "Deployment Limit must be a whole number." in ready.out()

    def test_an_empty_deployment_limit_means_the_default_of_one(self, ready):
        ready.set("Issue", "deployment_limit", "")
        ready.click("Issue Entitlement")
        assert ready.data()["payload"]["rights"]["deployment_limit"] == 1

    def test_a_missing_entitlement_file_is_an_error_and_the_window_keeps_working(self, ready):
        ready.click("Verify Entitlement")
        assert ready.out().startswith("ERROR: FileNotFoundError")
        ready.click("Issue Entitlement")
        ready.click("Verify Entitlement")
        assert ready.data()["allowed"] is True

    def test_a_corrupted_store_is_a_broken_report_but_an_error_when_listing(self, ready):
        ready.click("Issue Entitlement")
        ready.set("Deploy", "host", "a")
        ready.click("Record Deployment")
        store = ready.form("Deploy").get("store")
        text = open(store, encoding="utf-8").read()
        open(store, "w", encoding="utf-8").write(text[:30])
        ready.click("Generate Report")
        assert "BROKEN: unparseable_record at record index 0." in ready.out()
        ready.click("List All Records")
        assert "ERROR: RecordStoreError" in ready.out()

    def test_the_store_may_not_exist_yet_and_the_report_says_so(self, ready):
        ready.click("Generate Report")
        assert "this store file does not exist" in ready.out()


class TestLaunch:
    def test_no_display_is_an_entitle_error_the_command_line_can_print(self, window, monkeypatch):
        def no_display(self, *args, **kwargs):
            raise fake_tk.TclError("no display name and no $DISPLAY environment variable")

        monkeypatch.setattr(fake_tk.Tk, "__init__", no_display)
        with pytest.raises(EntitleError, match="Could not open a window: no display name"):
            window.module.launch()

    def test_launch_opens_the_window_and_runs_its_loop(self, window):
        fake_tk.reset()
        window.module.launch()
        assert len(fake_tk.NOTEBOOKS) == 1
