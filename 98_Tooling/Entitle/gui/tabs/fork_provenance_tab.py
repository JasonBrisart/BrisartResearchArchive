"""
Entitle GUI — Fork / Provenance Tab

Imports directly from ``entitle.tracking.fork`` and ``entitle.tracking.provenance``
(the submodules) rather than ``entitle.tracking`` (the package), since
``entitle/tracking/`` is a PEP 420 implicit namespace package with no
``__init__.py`` re-export layer.
"""
from tkinter import ttk

from entitle.tracking.fork import record_fork
from entitle.tracking.provenance import record_provenance
from entitle.paths import default_record_store
from gui.widgets import FormFrame

TAB_TITLE = "Fork / Provenance"


def build(parent, app):
    form = FormFrame(parent)
    form.add_entry("product", "Product ID", default="EntitleDemo")
    form.add_entry("source_version", "Source version (fork)")
    form.add_entry("fork_name", "Fork name")
    form.add_entry("maintainer", "Maintainer")
    form.add_entry("origin", "Origin (provenance)", default="JasonBrisart")
    form.add_entry("version", "Version (provenance)")
    form.add_entry("custodian", "Custodian (provenance)")
    form.add_entry("notes", "Notes (optional)")
    form.add_entry("store", "Record store file", default=default_record_store(), browse="save")

    def run_fork():
        try:
            record = record_fork(
                store=form.get("store"), product=form.get("product"), source_version=form.get("source_version"),
                fork_name=form.get("fork_name"), maintainer=form.get("maintainer"), notes=form.get("notes") or None,
            )
            app.show_json(record)
        except Exception as exc:
            app.show_error(exc)

    def run_provenance():
        try:
            record = record_provenance(
                store=form.get("store"), product=form.get("product"), origin=form.get("origin"),
                version=form.get("version"), custodian=form.get("custodian"), notes=form.get("notes") or None,
            )
            app.show_json(record)
        except Exception as exc:
            app.show_error(exc)

    row = form.next_row()
    ttk.Button(form, text="Record Fork", command=run_fork).grid(row=row, column=0, pady=12, sticky="w")
    ttk.Button(form, text="Record Provenance", command=run_provenance).grid(row=row, column=1, pady=12, sticky="w")
    return form
