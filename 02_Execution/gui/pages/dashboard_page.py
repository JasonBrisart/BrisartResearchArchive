from __future__ import annotations


def render(app):
    root = app.page_shell(
        "Dashboard",
        "A simple starting point for opening the main areas of the archive.",
    )

    app.add_card(
        root,
        2,
        "Workspace Menu",
        (
            "Use this page as a clean landing area. The sidebar contains the main navigation, "
            "and these buttons provide quick access to the primary sections."
        ),
        [
            ("Open Frameworks", lambda: app.show_page("Frameworks"), True),
            ("Open Results", lambda: app.show_page("Results"), False),
            ("Open Archive", lambda: app.show_page("Archive"), False),
            ("Open System", lambda: app.show_page("System"), False),
        ],
    )

    app.add_card(
        root,
        3,
        "Quick Actions",
        (
            "Run the currently selected framework or analyze available results. "
            "This card can be replaced later when the dashboard design is finalized."
        ),
        [
            ("Run Selected Framework", app.start_selected_framework, True),
            ("Analyze Results", app.analyze_tfl, False),
        ],
    )

    app.add_card(
        root,
        4,
        "Dashboard Placeholder",
        (
            "This dashboard is intentionally minimal for now. "
            "Future dashboard cards can be added here without changing the sidebar, "
            "page registry, framework system, or application shell."
        ),
    )