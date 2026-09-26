"""
File: gui/pages/archive_page.py

Purpose:
Render the Archive page: a single card that opens the local document
viewer for README files, framework notes, release notes, and protocol
drafts.

Communication / relationships:
- Registered as "Archive" in config/registries.get_page_registry().
- Rendered by gui/main_window.BrisartSuiteApp.show_page("Archive").
- The button calls app.open_local_doc(), which reaches
  gui/components/document_viewer.py through SystemController.

Settings / parameters:
- The card sits at grid row 2; rows 0 and 1 hold the page title and
  subtitle from page_shell().

Edge cases:
- The page is destroyed and rebuilt on every navigation and holds no
  state of its own.

Known limitations:
- There is no document index or browser; the user picks files through
  the file dialog.

Examples:
- app.show_page("Archive")
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
