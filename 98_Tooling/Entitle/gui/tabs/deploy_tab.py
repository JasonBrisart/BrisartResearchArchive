"""
File: gui/tabs/deploy_tab.py

Purpose
-------
Entitle GUI — Deploy Tab

Communication / relationships
-----------------------------
Direct module imports: tkinter, entitle.tracking.deploy, entitle.paths, gui.widgets.

Settings / parameters
---------------------
Module-level named settings: TAB_TITLE. See their definitions below for values.

Edge cases
----------
Additional edge-case guarantees are not established by this header; existing implementation and tests remain unchanged.

Known limitations
-----------------
This header update does not establish complete behavioral, platform, or security validation.

Examples
--------
Inspect the definitions below and the project documentation for supported usage.

Additional module documentation
-------------------------------
Entitle GUI — Deploy Tab

Imports directly from ``entitle.tracking.deploy`` (the submodule) rather than
``entitle.tracking`` (the package), since ``entitle/tracking/`` is a PEP 420
implicit namespace package with no ``__init__.py`` re-export layer.
"""

from tkinter import ttk

from entitle.tracking.deploy import deploy_from_file
from entitle.paths import default_entitlement_file, default_record_store
from gui.widgets import FormFrame

TAB_TITLE = "Deploy"


def build(parent, app):
    form = FormFrame(parent)
    form.add_entry("issuer", "Issuer ID", default="JasonBrisart")
    form.add_entry("subject", "Subject / Lab ID", default="ResearchLabA")
    form.add_entry("product", "Product ID", default="EntitleDemo")
    form.add_entry("master_key", "Master Key", show="*")
    form.add_entry("entitlement_path", "Entitlement file", default=default_entitlement_file(), browse="open")
    form.add_entry("host", "Host / node ID")
    form.add_entry("environment", "Environment (optional)")
    form.add_entry("notes", "Notes (optional)")
    form.add_entry("store", "Record store file", default=default_record_store(), browse="save")

    def run():
        try:
            outcome = deploy_from_file(
                issuer=form.get("issuer"), subject=form.get("subject"), product=form.get("product"),
                master_key=form.get("master_key"), entitlement_path=form.get("entitlement_path"),
                host=form.get("host"), store=form.get("store"),
                environment=form.get("environment") or None, notes=form.get("notes") or None,
            )
            app.show_json(outcome)
        except Exception as exc:
            app.show_error(exc)

    ttk.Button(form, text="Record Deployment", command=run).grid(row=form.next_row(), column=0, columnspan=3, pady=12, sticky="w")
    return form

