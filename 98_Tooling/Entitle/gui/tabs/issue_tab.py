"""
Entitle GUI — Issue Tab

Creates a protected offline entitlement container. Calls
``entitle.issue.issue_entitlement(...)`` directly -- the exact same function the
``python main.py issue ...`` CLI command uses.
"""
from tkinter import ttk

from entitle.issue import issue_entitlement
from entitle.paths import default_new_entitlement_file
from gui.widgets import FormFrame

TAB_TITLE = "Issue"


def build(parent, app):
    form = FormFrame(parent)
    form.add_entry("issuer", "Issuer ID", default="JasonBrisart")
    form.add_entry("subject", "Subject / Lab ID", default="ResearchLabA")
    form.add_entry("product", "Product ID", default="EntitleDemo")
    form.add_entry("entitlement_id", "Entitlement ID")
    form.add_entry("master_key", "Master Key", show="*")
    form.add_entry("drbg_seed", "DRBG Seed (>=64 chars)", show="*")
    form.add_entry("drbg_personalization", "DRBG Personalization (>=16 chars)")
    form.add_int_entry("deployment_limit", "Deployment Limit", default=1)
    form.add_entry("support_tier", "Support Tier", default="standard")
    form.add_entry("expires", "Expires (ISO timestamp, optional)")
    form.add_checkbox("enterprise", "Enterprise features")
    form.add_checkbox("modify", "Modify rights")
    form.add_checkbox("fork", "Fork rights")
    form.add_checkbox("export_source", "Source export rights")
    form.add_checkbox("redistribute", "Redistribution rights")
    form.add_entry(
        "output",
        "Output .entitle path",
        default=default_new_entitlement_file(),
        browse="save",
    )

    def run():
        try:
            payload = issue_entitlement(
                issuer=form.get("issuer"),
                subject=form.get("subject"),
                product=form.get("product"),
                entitlement_id=form.get("entitlement_id"),
                master_key=form.get("master_key"),
                drbg_seed=form.get("drbg_seed"),
                drbg_personalization=form.get("drbg_personalization"),
                output=form.get("output"),
                expires=form.get("expires") or None,
                enterprise=form.get_bool("enterprise"),
                modify=form.get_bool("modify"),
                fork=form.get_bool("fork"),
                export_source=form.get_bool("export_source"),
                redistribute=form.get_bool("redistribute"),
                deployment_limit=form.get_int("deployment_limit", 1),
                support_tier=form.get("support_tier"),
            )
            app.show_json({"created": form.get("output"), "payload": payload})
        except Exception as exc:
            app.show_error(exc)

    ttk.Button(form, text="Issue Entitlement", command=run).grid(
        row=form.next_row(), column=0, columnspan=3, pady=12, sticky="w"
    )
    return form
