"""
File: gui/tabs/tab_packages.py

Purpose
-------
The Packages tab: create, add/remove recipients on, open, and inspect the
custody chain of Identity-Bound Packages.

Public interface:
- class PackagesTab(ttk.Frame) -- Create, add/remove recipients on, open, and
  inspect the custody chain of Identity-Bound Packages.

Design notes:

"Run Demo" runs packages.demo.run_demo(), the same in-memory cycle as the
CLI's `demo` command, and shows its transcript in a read-only dialog. Nothing
is written to disk.

Typed master-key text becomes a key through packages.ciphers.text_master_key,
the same derivation as the CLI and demo. Opening a package as a recipient whose
part of it still uses the previous encryption first shows
gui.widgets.dialogs.migration_prompt(); OK migrates that recipient's key slot,
verifier, and the payload (packages.package.migrate_recipient) before opening,
Cancel opens it with the previous encryption.

Communication / relationships
-----------------------------
Depends on (project modules):
- gui.core.constants (gui/core/constants.py)
- gui.core.busy (gui/core/busy.py)
- gui.widgets.dialogs (gui/widgets/dialogs.py)
- packages.package (packages/package.py)
- packages.ciphers (packages/ciphers.py) -- text_master_key
- packages.custody (packages/custody.py)
- packages.demo (packages/demo.py)
- common.atomic_io (common/atomic_io.py)
Standard library: json, pathlib, tkinter.
Imported by:
- app.py
Covered by tests: gui/tests/test_tab_packages.py.

Settings / parameters
---------------------
No module-level constants, environment variables, or defaulted arguments:
behaviour is controlled entirely by the values callers pass in.

Edge cases
----------
- PackagesTab._create_package(): catches _Cancelled and handles it in place; it
  does not propagate to the caller.
- PackagesTab._create_package(): catches json.JSONDecodeError and handles it in
  place; it does not propagate to the caller.
- PackagesTab._load_state(): catches (OSError, json.JSONDecodeError,
  PackageError, CustodyError) and handles it in place; it does not propagate to
  the caller.
- PackagesTab._verify_custody(): catches (PackageError, CustodyError) and
  handles it in place; it does not propagate to the caller.

Known limitations
-----------------
- Master keys are typed text hashed once (packages.ciphers.text_master_key),
  not a password KDF: the same text always gives the same key, and a
  guessable text gives a guessable key. packages/main.py does the same for the
  CLI.
- _save_state() writes through common.atomic_io.atomic_write_json, so an
  interrupted save leaves the previous package file intact rather than a
  truncated one. It does not lock the file against a concurrent CLI save.
- Audit entries go to data/packages/audit, a path relative to the folder the
  GUI was started from, so launching from another folder writes the audit trail
  somewhere else.
- Requires a Tk display; there is no headless mode.

Examples
--------
Call shapes only, not a runnable script: master stands for a value the caller
supplies.

::

    from gui.tabs.tab_packages import PackagesTab
    PackagesTab(master)
"""

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from gui.core.constants import APP_TITLE, _Cancelled
from gui.core.busy import run_in_background
from gui.widgets.dialogs import TextPromptDialog, TextViewDialog, migration_prompt
from common.atomic_io import atomic_write_json
from packages import ciphers
from packages import package as ibp_package
from packages.custody import CustodyError
from packages.demo import run_demo
from packages.package import PackageError


class PackagesTab(ttk.Frame):
    """Create, add/remove recipients on, open, and inspect the custody chain
    of Identity-Bound Packages."""

    def __init__(self, master):
        super().__init__(master, padding=12)
        self.package_path = None
        self.state = None
        self._build_widgets()

    def _build_widgets(self):
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 8))
        ttk.Button(top, text="Choose Package File...", command=self._choose_path).pack(side="left")
        self._path_label = ttk.Label(top, text="(none selected)")
        self._path_label.pack(side="left", padx=8)

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(0, 8))
        ttk.Button(actions, text="Create Package...", command=self._create_package).pack(side="left")
        ttk.Button(actions, text="Add Recipient...", command=self._add_recipient).pack(side="left", padx=4)
        ttk.Button(actions, text="Remove Recipient...", command=self._remove_recipient).pack(side="left", padx=4)
        ttk.Button(actions, text="Open Package...", command=self._open_package).pack(side="left", padx=4)
        ttk.Button(actions, text="Verify Custody", command=self._verify_custody).pack(side="left", padx=4)
        ttk.Button(actions, text="Run Demo", command=self._run_demo).pack(side="right")

        ttk.Label(self, text="Recipients:").pack(anchor="w")
        columns = ("identity_id", "label")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=8, selectmode="browse")
        for col, width in zip(columns, (200, 280)):
            self.tree.heading(col, text=col.replace("_", " ").title())
            self.tree.column(col, width=width)
        self.tree.pack(fill="both", expand=True)

    def _choose_path(self):
        chosen = filedialog.asksaveasfilename(
            title="Package file", defaultextension=".json", initialfile="package.json",
            filetypes=[("Package files", "*.json"), ("All files", "*.*")],
        )
        if chosen:
            self.package_path = Path(chosen)
            self._path_label.configure(text=str(self.package_path))
            self._load_state(quiet=True)

    def _load_state(self, quiet=False):
        if self.package_path is None or not self.package_path.is_file():
            self.state = None
            self._refresh_recipients()
            return
        try:
            with open(self.package_path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            self.state = ibp_package.validate_package(raw)
        except (OSError, json.JSONDecodeError, PackageError, CustodyError) as exc:
            self.state = None
            if not quiet:
                messagebox.showerror(APP_TITLE, f"Could not load package: {exc}", parent=self)
        self._refresh_recipients()

    def _save_state(self):
        if self.package_path is None or self.state is None:
            return
        atomic_write_json(self.package_path, self.state)

    def _refresh_recipients(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        if self.state is None:
            return
        for recipient in ibp_package.list_recipients(self.state):
            self.tree.insert("", "end", values=(recipient["identity_id"], recipient["label"]))

    def _prompt_payload(self, initial='{\n  "message": "hello"\n}'):
        dialog = tk.Toplevel(self)
        dialog.title("Payload (JSON object)")
        dialog.transient(self)
        text = scrolledtext.ScrolledText(dialog, width=56, height=12, wrap="word")
        text.insert("1.0", initial)
        text.pack(fill="both", expand=True, padx=12, pady=12)
        result = {}

        def on_ok():
            result["value"] = text.get("1.0", "end").strip()
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        row = ttk.Frame(dialog, padding=(12, 0, 12, 12))
        row.pack(fill="x")
        ttk.Button(row, text="Cancel", command=on_cancel).pack(side="right")
        ttk.Button(row, text="OK", command=on_ok).pack(side="right", padx=(0, 8))
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        dialog.grab_set()
        dialog.wait_window(dialog)
        if "value" not in result:
            raise _Cancelled()
        return result["value"]

    def _create_package(self):
        if self.package_path is None:
            messagebox.showerror(APP_TITLE, "Choose a package file path first.", parent=self)
            return
        if self.package_path.is_file():
            messagebox.showerror(APP_TITLE, "A package file already exists at this path.", parent=self)
            return
        dialog = TextPromptDialog(
            self, "Create Package",
            [
                ("package_id", "Package id", False),
                ("identity_id", "Your identity id", False),
                ("label", "Your label", False),
                ("master_key", "Master key text (any text)", True),
            ],
        )
        if dialog.result is None:
            return
        values = dialog.result
        try:
            payload_text = self._prompt_payload()
        except _Cancelled:
            return
        package_id = values["package_id"].strip()
        identity_id = values["identity_id"].strip()
        label = values["label"].strip()
        if not package_id or not identity_id or not label:
            messagebox.showerror(APP_TITLE, "Package id, identity id, and label are required.", parent=self)
            return
        try:
            payload = json.loads(payload_text or "{}")
        except json.JSONDecodeError as exc:
            messagebox.showerror(APP_TITLE, f"Payload is not valid JSON: {exc}", parent=self)
            return
        master_key = ciphers.text_master_key(values["master_key"])
        audit_dir = Path("data") / "packages" / "audit"
        path = self.package_path

        def work():
            return ibp_package.create_package(
                package_id, label, payload, {identity_id: (label, master_key)}, audit_dir=audit_dir
            )

        def on_success(state):
            self.state = state
            self._save_state()
            self._refresh_recipients()
            messagebox.showinfo(APP_TITLE, f"Created package {package_id!r}.", parent=self)

        def on_error(exc):
            messagebox.showerror(APP_TITLE, str(exc), parent=self)

        run_in_background(self, work, on_success, on_error, "Creating package (sealing content key)...")

    def _add_recipient(self):
        if not self._require_state():
            return
        dialog = TextPromptDialog(
            self, "Add Recipient",
            [
                ("opener_id", "Your identity id (existing recipient)", False),
                ("opener_key", "Your master key text", True),
                ("new_id", "New recipient identity id", False),
                ("new_label", "New recipient label", False),
                ("new_key", "New recipient master key text", True),
            ],
        )
        if dialog.result is None:
            return
        values = dialog.result
        state = self.state
        opener_key = ibp_package.recipient_key_from_text(
            state, values["opener_id"].strip(), values["opener_key"]
        )
        new_key = ciphers.text_master_key(values["new_key"])
        audit_dir = Path("data") / "packages" / "audit"

        def work():
            return ibp_package.add_recipient(
                state, values["new_id"].strip(), values["new_label"].strip(), new_key,
                values["opener_id"].strip(), opener_key, audit_dir=audit_dir,
            )

        def on_success(updated):
            self.state = updated
            self._save_state()
            self._refresh_recipients()

        def on_error(exc):
            messagebox.showerror(APP_TITLE, str(exc), parent=self)

        run_in_background(self, work, on_success, on_error, "Adding recipient...")

    def _remove_recipient(self):
        if not self._require_state():
            return
        selection = self.tree.selection()
        default_id = self.tree.item(selection[0], "values")[0] if selection else ""
        dialog = TextPromptDialog(
            self, "Remove Recipient",
            [
                ("identity_id", f"Identity id to remove (default: {default_id})", False),
                ("opener_id", "Your identity id (authorizing this)", False),
                ("opener_key", "Your master key text", True),
            ],
        )
        if dialog.result is None:
            return
        values = dialog.result
        identity_id = values["identity_id"].strip() or default_id
        state = self.state
        opener_key = ibp_package.recipient_key_from_text(
            state, values["opener_id"].strip(), values["opener_key"]
        )
        audit_dir = Path("data") / "packages" / "audit"

        def work():
            return ibp_package.remove_recipient(
                state, identity_id, values["opener_id"].strip(), opener_key, audit_dir=audit_dir
            )

        def on_success(updated):
            self.state = updated
            self._save_state()
            self._refresh_recipients()

        def on_error(exc):
            messagebox.showerror(APP_TITLE, str(exc), parent=self)

        run_in_background(self, work, on_success, on_error, "Removing recipient...")

    def _open_package(self):
        if not self._require_state():
            return
        dialog = TextPromptDialog(
            self, "Open Package",
            [("identity_id", "Your identity id", False), ("master_key", "Master key text", True)],
        )
        if dialog.result is None:
            return
        values = dialog.result
        identity_id, text = values["identity_id"].strip(), values["master_key"]
        state = self.state
        audit_dir = Path("data") / "packages" / "audit"
        migrate = ibp_package.needs_encryption_migration(state, identity_id, text) and messagebox.askokcancel(
            APP_TITLE, migration_prompt(issues_recovery_code=False), parent=self,
        )

        def work():
            current = state
            if migrate:
                current = ibp_package.migrate_recipient(current, identity_id, text, audit_dir=audit_dir)
            master_key = ibp_package.recipient_key_from_text(current, identity_id, text)
            return ibp_package.open_package(current, identity_id, master_key, audit_dir=audit_dir)

        def on_success(result):
            payload, updated_state = result
            self.state = updated_state
            self._save_state()
            TextViewDialog(self, "Package Payload", json.dumps(payload, indent=2, sort_keys=True))

        def on_error(exc):
            messagebox.showerror(APP_TITLE, str(exc), parent=self)

        run_in_background(self, work, on_success, on_error, "Opening package...")

    def _verify_custody(self):
        if not self._require_state():
            return
        try:
            ibp_package.validate_package(self.state)
        except (PackageError, CustodyError) as exc:
            messagebox.showerror(APP_TITLE, f"Custody chain is invalid: {exc}", parent=self)
            return
        lines = [
            f"{entry['recorded_at']}  {entry['action']:<20} {entry['actor_label']}"
            for entry in ibp_package.custody_summary(self.state)
        ]
        TextViewDialog(self, "Custody Chain", "\n".join(lines) or "(empty)")

    def _require_state(self):
        if self.state is None:
            messagebox.showerror(APP_TITLE, "Choose and load a package file first.", parent=self)
            return False
        return True

    def _run_demo(self):
        """Run the in-memory demo and show its transcript."""

        def work():
            return "\n".join(run_demo()["transcript"])

        def on_success(transcript):
            TextViewDialog(self, "Package Demo", transcript)

        def on_error(exc):
            messagebox.showerror(APP_TITLE, str(exc), parent=self)

        run_in_background(self, work, on_success, on_error, "Running demo (real BSR2 derivations)...")
