from __future__ import annotations

import tkinter as tk

from config.registries import FRAMEWORK_REGISTRY
from gui.theme import COLORS, FONT_MONO


def render(app):
    root = app.page_shell(
        "Brisart Research Archive",
        "Local framework execution, analysis, documentation, and platform management.",
    )
    available_count = sum(1 for framework in FRAMEWORK_REGISTRY if framework["status"] == "Available")
    total_count = len(FRAMEWORK_REGISTRY)

    app.add_card(
        root, 2, "Launch Dashboard",
        (
            "This dashboard is the front door for the local research platform. "
            "Use it to start a framework, inspect results, open archive "
            "documentation, or manage system settings."
        ),
        [
            ("Run Selected Framework", app.start_selected_framework, True),
            ("Analyze Results", app.analyze_tfl, False),
            ("Open Archive", lambda: app.show_page("Archive"), False),
            ("System", lambda: app.show_page("System"), False),
        ],
    )
    app.add_card(
        root, 3, "Platform Status",
        (
            f"Application: {app.app_name}\n"
            f"Version: {app.app_version}\n"
            f"Execution Folder:\n{app.execution_dir}\n\n"
            f"Registered Frameworks: {total_count}\n"
            f"Available Frameworks: {available_count}\n"
            f"Selected Framework: {app.selected_framework.get()}"
        ),
    )
    app.add_card(
        root, 4, "Recommended Workflow",
        (
            "1. Select or inspect a framework.\n"
            "2. Run the available assay.\n"
            "3. Generate or inspect CSV output.\n"
            "4. Run local analysis.\n"
            "5. Review documentation and archive notes.\n"
            "6. Extend with additional framework modules over time."
        ),
        [
            ("Go to Frameworks", lambda: app.show_page("Frameworks"), False),
            ("Go to Results", lambda: app.show_page("Results"), False),
        ],
    )
    app.add_card(
        root, 5, "Engine / Shell Split",
        (
            "Each framework's trial logic lives in a headless, testable "
            "engine (see frameworks/<ID>/engine.py). The GUI only renders "
            "engine state and forwards input back into it, so trial logic "
            "can be verified by unit tests without ever opening a window."
        ),
    )
    app.add_card(
        root, 6, "Local-First Rule",
        (
            "The platform should remain readable, auditable, and usable as "
            "local Python source. Network behavior should remain limited, "
            "visible, and user-controlled."
        ),
    )

    app.home_log_box = tk.Text(
        root, height=10, bg=COLORS["panel"], fg=COLORS["text"],
        insertbackground=COLORS["accent"], relief="flat", font=FONT_MONO, wrap="word",
    )
    app.home_log_box.grid(row=7, column=0, sticky="ew", padx=26, pady=10)
    app.home_log_box.insert(
        "end",
        "Archive dashboard ready.\n"
        "Use the sidebar to open Frameworks, Results, Archive, or System.\n",
    )
