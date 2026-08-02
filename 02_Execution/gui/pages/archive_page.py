def render(app):
    root = app.page_shell(
        "Archive",
        "Local documentation, framework notes, release notes, standards, and lab-facing guidance.",
    )
    app.add_card(
        root, 2, "Open Archive Document",
        (
            "Open a local .txt or .md document inside the GUI. "
            "Use this for README files, framework notes, release notes, lab workflow documents, "
            "version rationales, and local protocol drafts."
        ),
        [("Open Document", app.open_local_doc, True)],
    )
    app.add_card(
        root, 3, "Lab Workflow",
        (
            "1. Select one framework.\n"
            "2. Run the baseline implementation.\n"
            "3. Export or inspect CSV output.\n"
            "4. Run local analysis.\n"
            "5. Validate locally.\n"
            "6. Integrate additional framework modules later."
        ),
    )
    app.add_card(
        root, 4, "Architecture Notes",
        (
            "The GUI is the front door. Underneath it, each framework is split "
            "into a headless engine (state, timing, validation, recording) and a "
            "thin GUI adapter that only renders engine state. Framework registry, "
            "framework services, shared runtime utilities, shared analysis, and "
            "the shared updater remain independent, swappable modules."
        ),
    )
    app.add_card(
        root, 5, "Framework Runner Rule",
        (
            "Framework-specific GUI trial flows live inside each framework "
            "package. For example, TFL is handled by frameworks/TFL/engine.py "
            "(logic) and frameworks/TFL/screen.py + session_gui.py (rendering). "
            "Future frameworks should follow the same engine/screen/session split."
        ),
    )
    app.add_card(
        root, 6, "Shared Layer Rule",
        (
            "Reusable execution infrastructure belongs in engine/ (timer "
            "abstractions) and frameworks/shared/ (schema). Framework-specific "
            "theory, stimuli, trial construction, feedback, and GUI behavior "
            "belong inside each framework package."
        ),
    )
    app.add_card(
        root, 7, "Future Archive Areas",
        (
            "- Framework README viewer\n"
            "- Release note viewer\n"
            "- Version rationale viewer\n"
            "- ARLA standards viewer\n"
            "- Lab setup checklist\n"
            "- Local implementation notes\n"
            "- Plugin/module documentation\n"
            "- Exportable validation reports"
        ),
    )
