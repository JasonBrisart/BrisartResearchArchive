"""
Entitle GUI — Revoke / Reinstate Tab

Revokes, reinstates, or checks the revocation status of an entitlement. Calls
``entitle.revoke.revoke(...)``, ``entitle.revoke.reinstate(...)``, and
``entitle.revoke.revocation_status(...)`` directly -- the same functions the
``python main.py revoke ...`` CLI subcommands use.
"""
from tkinter import ttk

from entitle.records import RecordStore
from entitle.revoke import reinstate, revocation_status, revoke
from entitle.paths import default_record_store
from gui.widgets import FormFrame

TAB_TITLE = "Revoke / Reinstate"


def build(parent, app):
    form = FormFrame(parent)
    form.add_entry("entitlement_id", "Entitlement ID")
    form.add_entry("issuer", "Issuer ID (optional)", default="JasonBrisart")
    form.add_entry("product", "Product ID (optional)", default="EntitleDemo")
    form.add_entry("reason", "Reason")
    form.add_entry(
        "store",
        "Record store file",
        default=default_record_store(),
        browse="save",
    )

    def run_revoke():
        try:
            store = RecordStore(form.get("store"))
            record = revoke(
                store,
                entitlement_id=form.get("entitlement_id"),
                issuer_id=form.get("issuer") or None,
                product_id=form.get("product") or None,
                reason=form.get("reason") or None,
            )
            app.show_json(record)
        except Exception as exc:
            app.show_error(exc)

    def run_reinstate():
        try:
            store = RecordStore(form.get("store"))
            record = reinstate(
                store,
                entitlement_id=form.get("entitlement_id"),
                issuer_id=form.get("issuer") or None,
                product_id=form.get("product") or None,
                reason=form.get("reason") or None,
            )
            app.show_json(record)
        except Exception as exc:
            app.show_error(exc)

    def run_check():
        try:
            store = RecordStore(form.get("store"))
            status = revocation_status(store, form.get("entitlement_id"))
            app.show_json(status)
        except Exception as exc:
            app.show_error(exc)

    row = form.next_row()
    ttk.Button(form, text="Revoke", command=run_revoke).grid(row=row, column=0, pady=12, sticky="w")
    ttk.Button(form, text="Reinstate", command=run_reinstate).grid(row=row, column=1, pady=12, sticky="w")
    ttk.Button(form, text="Check Status", command=run_check).grid(row=row, column=2, pady=12, sticky="w")
    return form
