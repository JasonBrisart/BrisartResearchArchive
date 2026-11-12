"""
File: gui/tabs.py

Purpose
-------
Hold everything the window shows inside its notebook: the seven workflow tabs (Keys, Issue,
  Verify, Deploy, Fork / Provenance, Revoke / Reinstate, Audit Report), the one form layout they
  all use, and what the forms are pre-filled with. Each button calls the same entitle/ function
  as the matching command-line command, so the window adds no rules of its own.

Communication / relationships
-----------------------------
Imports tkinter (tk, ttk, filedialog, messagebox) and, from the application,
  entitle/entitlements.py (issue, verify, inspect, migrate), entitle/signing.py (key pairs and
  key files), entitle/host.py (machine_fingerprint), entitle/records.py (RecordStore),
  entitle/revoke.py, entitle/revocation_list.py (publish), entitle/tracking.py (deploy,
  release, fork, provenance), entitle/checkpoints.py and entitle/report.py. Imported only by
  gui/window.py, which adds TABS to its notebook in order. Every button runs through
  app.run(action) from gui/window.py, which shows the result or the error; nothing here imports
  the window. Covered by tests/test_gui.py.

Settings / parameters
---------------------
TABS is the ordered (title, builder) list. Pre-filled values: the demo identity JasonBrisart,
  ResearchLabA and EntitleDemo (as in docs/README.md); ENTITLEMENT_FILE, RECORD_STORE,
  PUBLIC_KEY_FILE (keys/issuer.public-key), REVOCATION_LIST_FILE and CHECKPOINT_FILE under the
  Entitle folder; and SIGNING_KEY_FILE in EntitleKeys in the home folder, outside any
  repository. Fields created with shared=True (issuer, subject, product, master key, signing
  key, passphrase, public key, entitlement file, store) are one variable across every tab, so
  nothing is retyped. The master key and passphrase are masked. Issue signs with the signing key
  unless "Sign with the signing key" is cleared, in which case it uses the master key. The
  deployment limit field reads blank as 1 and "unlimited" as no limit; bound machines are
  comma-separated fingerprints.

Edge cases
----------
Before anything replaces an existing file (Issue, Generate Key Pair, Create Checkpoint) the
  window asks; declining writes nothing and shows "Cancelled: nothing was written.". Verify and
  Deploy pick the key the file needs: the public key for a signed file, the master key for a
  shared-key file (and the public key as well when a revocation list is given). Verify adds a
  "note" to an allowed shared-key result (convert it to signed) or previous-format result
  (migrate it). A deployment limit that is not a whole number is refused here by field name;
  every other check is done by entitle/ and shown as an error. Optional fields left empty are
  passed as None. A refused deployment or release is shown as the returned outcome, not an
  error. Browse uses a save dialog where the file may not exist yet and an open dialog otherwise.

Known limitations
-----------------
No field for custom payload metadata or for the shared-key DRBG options (the command line keeps
  them). The forms do not remember values between runs, so the passphrase is typed once per
  session. Layout is a single column; on a small screen the output pane is what shrinks.

Examples
--------
The tabs are only built by the window; from the directory containing run.py:

    python run.py
"""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from entitle.checkpoints import create_checkpoint, verify_checkpoint
from entitle.entitlements import (
    inspect_entitlement,
    is_signed,
    issue_entitlement,
    migrate_entitlement,
    read_entitlement_file,
    uses_previous_encryption,
    verify_entitlement,
)
from entitle.host import machine_fingerprint
from entitle.records import RecordStore
from entitle.report import build_report, format_text
from entitle.revocation_list import publish_revocation_list
from entitle.revoke import reinstate, revocation_status, revoke
from entitle.signing import generate_key_pair, load_public_key, load_public_keys, load_signing_key
from entitle.tracking import deploy_from_file, record_fork, record_provenance, release_deployment

_ENTITLE_FOLDER = Path(__file__).resolve().parent.parent
ENTITLEMENT_FILE = str(_ENTITLE_FOLDER / "entitlements" / "lab_a.entitle")
RECORD_STORE = str(_ENTITLE_FOLDER / "records" / "entitle_records.log")
SIGNING_KEY_FILE = str(Path.home() / "EntitleKeys" / "issuer.signing-key")
PUBLIC_KEY_FILE = str(_ENTITLE_FOLDER / "keys" / "issuer.public-key")
REVOCATION_LIST_FILE = str(_ENTITLE_FOLDER / "entitlements" / "revoked.entitle-crl")
CHECKPOINT_FILE = str(_ENTITLE_FOLDER / "reports" / "log.entitle-checkpoint")
DEMO_ISSUER = "JasonBrisart"
DEMO_SUBJECT = "ResearchLabA"
DEMO_PRODUCT = "EntitleDemo"
PREVIOUS_ENCRYPTION_NOTE = (
    "This file still uses the previous encryption (BSR2 Alpha 3). "
    "Press Migrate to Current Encryption to re-seal it."
)
SHARED_KEY_NOTE = (
    "This is a shared-key entitlement: anyone who can verify it can also issue one. "
    "Press Convert to Signed to replace it with a signed entitlement."
)
CANCELLED = "Cancelled: nothing was written."


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

    def add_signing_key(self):
        self.add_entry("signing_key", "Signing key file", default=SIGNING_KEY_FILE, browse="open", shared=True)
        self.add_entry("passphrase", "Signing key passphrase", show="*", shared=True)

    def add_verification_keys(self):
        self.add_entry("public_key", "Issuer public key file", default=PUBLIC_KEY_FILE, browse="open", shared=True)
        self.add_entry("master_key", "Master key (shared-key files only)", show="*", shared=True)

    def add_store(self, browse="save"):
        self.add_entry("store", "Record store file", default=RECORD_STORE, browse=browse, shared=True)

    def add_checkbox(self, key, label, *, default=False):
        var = tk.BooleanVar(value=default)
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

    def get_list(self, key):
        return [item.strip() for item in self.vars[key].get().split(",") if item.strip()]

    def store(self):
        return RecordStore(self.get("store"))

    def identity(self):
        return dict(issuer=self.get("issuer"), subject=self.get("subject"), product=self.get("product"))

    def signing_key(self):
        """The signing key from the shared fields (set on the Keys tab or any tab that shows them)."""
        shared = self.app.shared
        return load_signing_key(shared["signing_key"].get(), shared["passphrase"].get())

    def public_keys(self):
        return load_public_keys([self.get("public_key")]) if self.get("public_key").strip() else None

    def keys_for(self, path, *, revocation_list=None):
        """(master_key, public_keys) that the entitlement file at path needs.

        A signed file needs the public key. A shared-key file needs the master key, and the public
        key too only when a (signed) revocation list is to be checked.
        """
        if is_signed(read_entitlement_file(path)):
            return None, self.public_keys()
        return self.optional("master_key"), self.public_keys() if revocation_list else None


def _may_write(path):
    """True when path is new or the operator agrees to replace it."""
    return not Path(path).exists() or messagebox.askyesno("Entitle", f"{path} already exists. Replace it?")


def _keys_tab(parent, app):
    form = FormFrame(parent, app)
    form.add_entry("key_name", "Key name (usually the issuer ID)", default=DEMO_ISSUER)
    form.add_signing_key()
    form.add_entry("public_key", "Public key file", default=PUBLIC_KEY_FILE, browse="save", shared=True)

    def generate():
        for path in (form.get("signing_key"), form.get("public_key")):
            if not _may_write(path):
                return CANCELLED
        public = generate_key_pair(
            name=form.get("key_name"), signing_key_path=form.get("signing_key"),
            public_key_path=form.get("public_key"), passphrase=form.get("passphrase"), overwrite=True,
        )
        return {"created": {"signing_key": form.get("signing_key"), "public_key": form.get("public_key")},
                "public_key": public.to_dict(),
                "note": "Keep the signing key and its passphrase private. Give the public key to every verifier."}

    def show():
        return load_public_key(form.get("public_key")).to_dict()

    def fingerprint():
        return {"machine_fingerprint": machine_fingerprint()}

    form.add_buttons(("Generate Key Pair", generate), ("Show Public Key", show), ("This Machine's Fingerprint", fingerprint))
    return form


def _issue_tab(parent, app):
    form = FormFrame(parent, app)
    form.add_identity()
    form.add_entry("entitlement_id", "Entitlement ID")
    form.add_checkbox("signed", "Sign with the signing key (recommended)", default=True)
    form.add_signing_key()
    form.add_entry("master_key", "Master key (shared-key only)", show="*", shared=True)
    form.add_entry("deployment_limit", "Deployment limit (blank = 1, 'unlimited')", default="1")
    form.add_entry("support_tier", "Support tier", default="standard")
    form.add_entry("expires", "Expires (ISO timestamp, optional)")
    form.add_entry("not_before", "Not before (ISO timestamp, signed only)")
    form.add_entry("machines", "Bound machines (fingerprints, comma-separated)")
    form.add_checkbox("enterprise", "Enterprise features")
    form.add_checkbox("modify", "Modify rights")
    form.add_checkbox("fork", "Fork rights")
    form.add_checkbox("export_source", "Source export rights")
    form.add_checkbox("redistribute", "Redistribution rights")
    form.add_entry("entitlement_file", "Output .entitle path", default=ENTITLEMENT_FILE, browse="save", shared=True)

    def issue():
        output = form.get("entitlement_file")
        if not _may_write(output):
            return CANCELLED
        signed = form.get_bool("signed")
        limit = None if form.get("deployment_limit").strip().lower() == "unlimited" else form.get_int("deployment_limit")
        payload = issue_entitlement(
            **form.identity(),
            entitlement_id=form.get("entitlement_id"),
            signing_key=form.signing_key() if signed else None,
            master_key=None if signed else form.get("master_key"),
            output=output,
            expires=form.optional("expires"),
            not_before=form.optional("not_before"),
            machines=form.get_list("machines"),
            enterprise=form.get_bool("enterprise"),
            modify=form.get_bool("modify"),
            fork=form.get_bool("fork"),
            export_source=form.get_bool("export_source"),
            redistribute=form.get_bool("redistribute"),
            deployment_limit=limit,
            support_tier=form.get("support_tier"),
            overwrite=True,
        )
        return {"created": output, "signed": signed, "payload": payload}

    form.add_buttons(("Issue Entitlement", issue))
    return form


def _verify_tab(parent, app):
    form = FormFrame(parent, app)
    form.add_identity()
    form.add_verification_keys()
    form.add_entry("entitlement_file", "Entitlement file", default=ENTITLEMENT_FILE, browse="open", shared=True)
    form.add_entry("revocation_list", "Revocation list (optional)", browse="open")

    def verify():
        path = form.get("entitlement_file")
        listing = form.optional("revocation_list")
        master_key, public_keys = form.keys_for(path, revocation_list=listing)
        result = verify_entitlement(
            **form.identity(), path=path, master_key=master_key, public_keys=public_keys, revocation_list=listing,
        ).to_dict()
        if result["allowed"] and uses_previous_encryption(path):
            result["note"] = PREVIOUS_ENCRYPTION_NOTE
        elif result["allowed"] and master_key is not None:
            result["note"] = SHARED_KEY_NOTE
        return result

    def inspect():
        return inspect_entitlement(form.get("entitlement_file"))

    def migrate():
        return migrate_entitlement(**form.identity(), master_key=form.get("master_key"), path=form.get("entitlement_file"))

    def convert():
        return migrate_entitlement(
            **form.identity(), master_key=form.get("master_key"), path=form.get("entitlement_file"),
            signing_key=form.signing_key(),
        )

    form.add_buttons(("Verify Entitlement", verify), ("Inspect", inspect),
                     ("Migrate to Current Encryption", migrate), ("Convert to Signed", convert))
    return form


def _deploy_tab(parent, app):
    form = FormFrame(parent, app)
    form.add_identity()
    form.add_verification_keys()
    form.add_entry("entitlement_file", "Entitlement file", default=ENTITLEMENT_FILE, browse="open", shared=True)
    form.add_entry("host", "Host / node ID")
    form.add_entry("environment", "Environment (optional)")
    form.add_entry("notes", "Notes (optional)")
    form.add_entry("release_entitlement_id", "Entitlement ID (release only)")
    form.add_store()

    def deploy():
        path = form.get("entitlement_file")
        master_key, public_keys = form.keys_for(path)
        return deploy_from_file(
            **form.identity(),
            master_key=master_key,
            public_keys=public_keys,
            entitlement_path=path,
            host=form.get("host"),
            store=form.store(),
            environment=form.optional("environment"),
            notes=form.optional("notes"),
        )

    def release():
        return release_deployment(
            form.store(), product=form.get("product"), subject=form.get("subject"),
            entitlement_id=form.get("release_entitlement_id"), host=form.get("host"), reason=form.optional("notes"),
        )

    form.add_buttons(("Record Deployment", deploy), ("Release Deployment", release))
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
    form.add_entry("issuer", "Issuer ID", default=DEMO_ISSUER, shared=True)
    form.add_entry("product", "Product ID (optional)", default=DEMO_PRODUCT, shared=True)
    form.add_entry("reason", "Reason")
    form.add_store()
    form.add_signing_key()
    form.add_entry("revocation_list", "Revocation list to publish", default=REVOCATION_LIST_FILE, browse="save")

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

    def publish():
        return publish_revocation_list(
            form.store(), form.signing_key(), issuer=form.get("issuer"), output=form.get("revocation_list")
        )

    form.add_buttons(("Revoke", revoke_it), ("Reinstate", reinstate_it), ("Check Status", check),
                     ("Publish Revocation List", publish))
    return form


def _report_tab(parent, app):
    form = FormFrame(parent, app)
    form.add_store(browse="open")
    form.add_entry("checkpoint", "Checkpoint file", default=CHECKPOINT_FILE, browse="save")
    form.add_signing_key()
    form.add_entry("public_key", "Issuer public key file", default=PUBLIC_KEY_FILE, browse="open", shared=True)

    def report():
        return format_text(build_report(form.store()))

    def records():
        return form.store().filter()

    def checkpoint():
        if not _may_write(form.get("checkpoint")):
            return CANCELLED
        return create_checkpoint(form.store(), form.signing_key(), output=form.get("checkpoint"), overwrite=True)

    def check_checkpoint():
        return verify_checkpoint(form.store(), form.get("checkpoint"), form.public_keys() or [])

    form.add_buttons(("Generate Report", report), ("List All Records", records),
                     ("Create Checkpoint", checkpoint), ("Verify Checkpoint", check_checkpoint))
    return form


TABS = (
    ("Keys", _keys_tab),
    ("Issue", _issue_tab),
    ("Verify", _verify_tab),
    ("Deploy", _deploy_tab),
    ("Fork / Provenance", _fork_provenance_tab),
    ("Revoke / Reinstate", _revoke_tab),
    ("Audit Report", _report_tab),
)
