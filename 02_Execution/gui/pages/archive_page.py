"""
File: gui/pages/archive_page.py

Purpose
-------
Render the Archive page: open local documentation (README files, notes,
release notes, protocol drafts) in the read-only viewer.

Communication / relationships
-----------------------------
- Rendered by gui/main_window.show_page("Archive") through
  gui/navigation.py.
- The button calls app.open_local_doc(), which opens
  gui/components/document_viewer.py.

Settings / parameters
---------------------
- One card at grid row 2.

Edge cases
----------
- Holds no state; rebuilt on every visit.

Known limitations
-----------------
- No document index; documents are picked through the file dialog.

Examples
--------
- app.show_page("Archive")
"""
def render(app):
    root = app.page_shell("Archive", "Open local documentation and release files.")
    app.add_card(
        root, 2, "Open Archive Document",
        "Open a local .txt or .md file, such as docs/CHANGELOG.md or a protocol draft.",
        [("Open Document", app.open_local_doc, True)],
    )
