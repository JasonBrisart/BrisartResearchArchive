"""
File: gui/tabs.py

Purpose
-------
Hold everything the window shows inside its notebook: the six workflow tabs (Issue, Verify,
  Deploy, Fork / Provenance, Revoke / Reinstate, Audit Report), the one form layout they all
  use, and what the forms are pre-filled with. Each button calls the same entitle/ function as
  the matching command-line command, so the window adds no rules of its own.

Communication / relationships
-----------------------------
Imports tkinter (tk, ttk, filedialog) and, from the application, entitle/entitlements.py (issue,
  verify, migrate), entitle/records.py (RecordStore), entitle/revoke.py, entitle/tracking.py and
  entitle/report.py. Imported only by gui/window.py, which adds TABS to its notebook in order.
  Every button runs through app.run(action) from gui/window.py, which shows the result or the
  error; nothing here imports the window, so there is no import cycle. Covered by
  tests/test_gui.py.

Settings / parameters
---------------------
TABS is the ordered (title, builder) list. Pre-filled values: the demo identity JasonBrisart,
  ResearchLabA and EntitleDemo (the same as docs/README.md), ENTITLEMENT_FILE
  (entitlements/lab_a.entitle) and RECORD_STORE (records/entitle_records.log), both under the
  Entitle folder so the window works from any working folder. Fields created with shared=True
  (issuer, subject, product, master key, entitlement file, store) are one variable across every
  tab, so nothing is retyped between Issue, Verify and Deploy. The master key and DRBG seed are
  masked. FormFrame.get_int reads an empty field as its default (1 for the deployment limit).

Edge cases
----------
A deployment limit that is not a whole number is refused here by field name before anything is
  issued; every other input check (blank IDs, a bad expiry, a negative limit, short keys) is
  done by entitle/ and shown as an error. Optional fields left empty are passed as None, so they
  are stored as null rather than as empty text. Verify adds a "note" to an allowed result when
  the file still uses the previous encryption; Migrate to Current Encryption re-seals it and
  reports already_current_encryption for a current file. A refused deployment is shown as the
  returned outcome ("recorded": false), not as an error. Browse uses a save dialog where the
  file may not exist yet (issue output, record store) and an open dialog otherwise.

Known limitations
-----------------
No field for custom payload metadata, no confirmation before Issue overwrites an existing file,
  and no way to issue an unlimited deployment limit. The forms do not remember values between
  runs. Layout is a single column sized for the default 880x640 window.

Examples
--------
The tabs are only built by the window; from the directory containing main.py:

    python main.py gui
"""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from entitle.entitlements import issue_entitlement, migrate_entitlement, uses_previous_encryption, verify_entitlement
from entitle.records import RecordStore
from entitle.report import build_report, format_text
from entitle.revoke import reinstate, revocation_status, revoke
from entitle.tracking import deploy_from_file, record_fork, record_provenance

_ENTITLE_FOLDER = Path(__file__).resolve().parent.parent
ENTITLEMENT_FILE = str(_ENTITLE_FOLDER / "entitlements" / "lab_a.entitle")
RECORD_STORE = str(_ENTITLE_FOLDER / "records" / "entitle_records.log")
DEMO_ISSUER = "JasonBrisart"
DEMO_SUBJECT = "ResearchLabA"
DEMO_PRODUCT = "EntitleDemo"

PREVIOUS_ENCRYPTION_NOTE = (
    "This file still uses the previous encryption (BSR2 Alpha 3). "
    "Press Migrate to Current Encryption to re-seal it."
)


class FormFrame(ttk.Frame):
    """A single-column form whose buttons report through the window's output pane."""

    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self.app = app
        self._row = 0
        self.vars = {}
        self.labels = {}
        self.grid_columnconfigure(1, weight=1)

    def add_entry(self, key, label, *, default="", show=None, browse=None, shared=False):
        ttk.Label(self, text=label).grid(row=self._row, column=0, sticky="w", pady=3)
        if shared:
            var = self.app.shared.setdefault(key, tk.StringVar(value=default))
        else:
            var = tk.StringVar(value=default)
        ttk.Entry(self, textvariable=var, width=48, show=show or "").grid(
            row=self._row, column=1, sticky="we", padx=6, pady=3
        )
        self.vars[key] = var
        self.labels[key] = label
        if browse is not None:
            ttk.Button(self, text="Browse…", command=lambda: self._browse(var, browse)).grid(
                row=self._row, column=2, padx=(0, 6)
            )
        self._row += 1
        return var

    def add_identity(self):
        self.add_entry("issuer", "Issuer ID", default=DEMO_ISSUER, shared=True)
        self.add_entry("subject", "Subject / Lab ID", default=DEMO_SUBJECT, shared=True)
        self.add_entry("product", "Product ID", default=DEMO_PRODUCT, shared=True)
        self.add_entry("master_key", "Master Key", show="*", shared=True)

    def add_store(self, browse="save"):
        self.add_entry("store", "Record store file", default=RECORD_STORE, browse=browse, shared=True)

    def add_checkbox(self, key, label):
        var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self, text=label, variable=var).grid(
            row=self._row, column=0, columnspan=2, sticky="w", pady=2
        )
        self.vars[key] = var
        self._row += 1
        return var

    def add_buttons(self, *buttons):
        for column, (text, action) in enumerate(buttons):
            ttk.Button(self, text=text, command=self.app.run(action)).grid(
                row=self._row, column=column, pady=12, padx=(0, 6), sticky="w"
            )
        self._row += 1

    def _browse(self, var, mode):
        if mode == "save":
            path = filedialog.asksaveasfilename(title="Select output path")
        else:
            path = filedialog.askopenfilename(title="Select file")
        if path:
            var.set(path)

    def get(self, key):
        return self.vars[key].get()

    def optional(self, key):
        return self.vars[key].get() or None

    def get_int(self, key, default=1):
        raw = self.vars[key].get().strip()
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            raise ValueError(f"{self.labels[key]} must be a whole number.") from None

    def get_bool(self, key):
        return self.vars[key].get()

    def store(self):
        return RecordStore(self.get("store"))

    def identity(self):
        return dict(
            issuer=self.get("issuer"),
            subject=self.get("subject"),
            product=self.get("product"),
            master_key=self.get("master_key"),
        )


def _issue_tab(parent, app):
    form = FormFrame(parent, app)
    form.add_identity()
    form.add_entry("entitlement_id", "Entitlement ID")
    form.add_entry("drbg_seed", "DRBG Seed (optional, >=64 chars)", show="*")
    form.add_entry("drbg_personalization", "DRBG Personalization (optional, >=16 chars)")
    form.add_entry("deployment_limit", "Deployment Limit", default="1")
    form.add_entry("support_tier", "Support Tier", default="standard")
    form.add_entry("expires", "Expires (ISO timestamp, optional)")
    form.add_checkbox("enterprise", "Enterprise features")
    form.add_checkbox("modify", "Modify rights")
    form.add_checkbox("fork", "Fork rights")
    form.add_checkbox("export_source", "Source export rights")
    form.add_checkbox("redistribute", "Redistribution rights")
    form.add_entry("entitlement_file", "Output .entitle path", default=ENTITLEMENT_FILE, browse="save", shared=True)

    def issue():
        payload = issue_entitlement(
            **form.identity(),
            entitlement_id=form.get("entitlement_id"),
            drbg_seed=form.optional("drbg_seed"),
            drbg_personalization=form.optional("drbg_personalization"),
            output=form.get("entitlement_file"),
            expires=form.optional("expires"),
            enterprise=form.get_bool("enterprise"),
            modify=form.get_bool("modify"),
            fork=form.get_bool("fork"),
            export_source=form.get_bool("export_source"),
            redistribute=form.get_bool("redistribute"),
            deployment_limit=form.get_int("deployment_limit"),
            support_tier=form.get("support_tier"),
        )
        return {"created": form.get("entitlement_file"), "payload": payload}

    form.add_buttons(("Issue Entitlement", issue))
    return form


def _verify_tab(parent, app):
    form = FormFrame(parent, app)
    form.add_identity()
    form.add_entry("entitlement_file", "Entitlement file", default=ENTITLEMENT_FILE, browse="open", shared=True)

    def verify():
        result = verify_entitlement(**form.identity(), path=form.get("entitlement_file")).to_dict()
        if result["allowed"] and uses_previous_encryption(form.get("entitlement_file")):
            result["note"] = PREVIOUS_ENCRYPTION_NOTE
        return result

    def migrate():
        return migrate_entitlement(**form.identity(), path=form.get("entitlement_file"))

    form.add_buttons(("Verify Entitlement", verify), ("Migrate to Current Encryption", migrate))
    return form


def _deploy_tab(parent, app):
    form = FormFrame(parent, app)
    form.add_identity()
    form.add_entry("entitlement_file", "Entitlement file", default=ENTITLEMENT_FILE, browse="open", shared=True)
    form.add_entry("host", "Host / node ID")
    form.add_entry("environment", "Environment (optional)")
    form.add_entry("notes", "Notes (optional)")
    form.add_store()

    def deploy():
        return deploy_from_file(
            **form.identity(),
            entitlement_path=form.get("entitlement_file"),
            host=form.get("host"),
            store=form.store(),
            environment=form.optional("environment"),
            notes=form.optional("notes"),
        )

    form.add_buttons(("Record Deployment", deploy))
    return form


def _fork_provenance_tab(parent, app):
    form = FormFrame(parent, app)
    form.add_entry("product", "Product ID", default=DEMO_PRODUCT, shared=True)
    form.add_entry("source_version", "Source version (fork)")
    form.add_entry("fork_name", "Fork name")
    form.add_entry("maintainer", "Maintainer")
    form.add_entry("environment", "Environment (fork, optional)")
    form.add_entry("origin", "Origin (provenance)", default=DEMO_ISSUER)
    form.add_entry("version", "Version (provenance)")
    form.add_entry("custodian", "Custodian (provenance)")
    form.add_entry("previous_version", "Previous version (provenance, optional)")
    form.add_entry("notes", "Notes (optional)")
    form.add_store()

    def fork():
        return record_fork(
            form.store(),
            product=form.get("product"),
            source_version=form.get("source_version"),
            fork_name=form.get("fork_name"),
            maintainer=form.get("maintainer"),
            environment=form.optional("environment"),
            notes=form.optional("notes"),
        )

    def provenance():
        return record_provenance(
            form.store(),
            product=form.get("product"),
            origin=form.get("origin"),
            version=form.get("version"),
            custodian=form.get("custodian"),
            previous_version=form.optional("previous_version"),
            notes=form.optional("notes"),
        )

    form.add_buttons(("Record Fork", fork), ("Record Provenance", provenance))
    return form


def _revoke_tab(parent, app):
    form = FormFrame(parent, app)
    form.add_entry("entitlement_id", "Entitlement ID")
    form.add_entry("issuer", "Issuer ID (optional)", default=DEMO_ISSUER, shared=True)
    form.add_entry("product", "Product ID (optional)", default=DEMO_PRODUCT, shared=True)
    form.add_entry("reason", "Reason")
    form.add_store()

    def details():
        return dict(
            issuer_id=form.optional("issuer"), product_id=form.optional("product"), reason=form.optional("reason")
        )

    def revoke_it():
        return revoke(form.store(), form.get("entitlement_id"), **details())

    def reinstate_it():
        return reinstate(form.store(), form.get("entitlement_id"), **details())

    def check():
        return revocation_status(form.store(), form.get("entitlement_id"))

    form.add_buttons(("Revoke", revoke_it), ("Reinstate", reinstate_it), ("Check Status", check))
    return form


def _report_tab(parent, app):
    form = FormFrame(parent, app)
    form.add_store(browse="open")

    def report():
        return format_text(build_report(form.store()))

    def records():
        return form.store().filter()

    form.add_buttons(("Generate Report", report), ("List All Records", records))
    return form


TABS = (
    ("Issue", _issue_tab),
    ("Verify", _verify_tab),
    ("Deploy", _deploy_tab),
    ("Fork / Provenance", _fork_provenance_tab),
    ("Revoke / Reinstate", _revoke_tab),
    ("Audit Report", _report_tab),
)
