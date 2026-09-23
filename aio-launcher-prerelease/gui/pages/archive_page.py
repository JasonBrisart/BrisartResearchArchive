"""
gui/pages/archive_page.py
The Archive page: a single card that opens the local .txt/.md document
viewer (gui.components.document_viewer, via app.open_local_doc) for
browsing README/notes/release/protocol documents inside the GUI.
Registered as the "Archive" page in config.registries.get_page_registry().
"""
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
