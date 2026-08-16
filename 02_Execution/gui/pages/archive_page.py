def render(app):
    root = app.page_shell(
        "Archive",
        "Open local documentation, framework notes, and release files.",
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
