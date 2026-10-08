"""
Entitle GUI — Audit Report Tab

Builds an audit report over the tamper-evident record store, including hash chain
verification. Calls ``entitle.report.build_report_for_path(...)`` and
``entitle.report.format_text(...)`` directly -- the same functions the
``python main.py report ...`` CLI command uses.
"""
from tkinter import ttk

from entitle.report import build_report_for_path, format_text
from entitle.paths import default_record_store
from gui.widgets import FormFrame

TAB_TITLE = "Audit Report"


def build(parent, app):
    form = FormFrame(parent)
    form.add_entry(
        "store",
        "Record store file",
        default=default_record_store(),
        browse="open",
    )

    def run():
        try:
            report = build_report_for_path(form.get("store"))
            app.show_text(format_text(report))
        except Exception as exc:
            app.show_error(exc)

    ttk.Button(form, text="Generate Report", command=run).grid(
        row=form.next_row(), column=0, columnspan=3, pady=12, sticky="w"
    )
    return form
