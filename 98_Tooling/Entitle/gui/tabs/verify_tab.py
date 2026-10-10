"""
File: gui/tabs/verify_tab.py

Purpose
-------
Entitle GUI — Verify Tab

Communication / relationships
-----------------------------
Direct module imports: tkinter, entitle.verify, entitle.paths, gui.widgets.

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
Entitle GUI — Verify Tab

Verifies a protected entitlement container. Calls
``entitle.verify.verify_entitlement(...)`` directly -- the exact same function
the ``python main.py verify ...`` CLI command uses.
"""

from tkinter import ttk

from entitle.verify import verify_entitlement
from entitle.paths import default_entitlement_file
from gui.widgets import FormFrame

TAB_TITLE = "Verify"


def build(parent, app):
    form = FormFrame(parent)
    form.add_entry("issuer", "Issuer ID", default="JasonBrisart")
    form.add_entry("subject", "Subject / Lab ID", default="ResearchLabA")
    form.add_entry("product", "Product ID", default="EntitleDemo")
    form.add_entry("master_key", "Master Key", show="*")
    form.add_entry(
        "file",
        "Entitlement file",
        default=default_entitlement_file(),
        browse="open",
    )

    def run():
        try:
            result = verify_entitlement(
                issuer=form.get("issuer"),
                subject=form.get("subject"),
                product=form.get("product"),
                master_key=form.get("master_key"),
                file=form.get("file"),
            )
            app.show_json(result.to_dict())
        except Exception as exc:
            app.show_error(exc)

    ttk.Button(form, text="Verify Entitlement", command=run).grid(
        row=form.next_row(), column=0, columnspan=3, pady=12, sticky="w"
    )
    return form

