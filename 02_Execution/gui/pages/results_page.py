"""
File: gui/pages/results_page.py

Purpose
-------
Render the Results page: pick one or several saved TFL sessions from a
list, analyze them (one session gives the reference report, several are
pooled), open their CSV files, and show the report.

Communication / relationships
-----------------------------
- Rendered by gui/main_window.show_page("Results") through
  gui/navigation.py.
- Lists sessions with frameworks/TFL/output.list_session_files() in the
  folder from app.tfl_output_dir(); the page owns the list and its
  selection.
- Buttons call app.analyze_tfl(paths), app.choose_tfl_sessions(),
  app.open_tfl_csvs(paths), and app.open_tfl_folder().
- SystemController.set_analysis_text() writes reports into
  app.analysis_box; frameworks/TFL/gui_session.py shows this page and calls
  app.analyze_tfl(path) for the run that just finished.
- Uses bind_scroll_passthrough() from gui/components/page_helpers.py for the
  list and the report box.

Settings / parameters
---------------------
- Session list: newest first, one line per file (saved date and name),
  extended selection: click one, Ctrl+click to add, Shift+click for a
  range.
- The newest session is selected when the page opens, so one click on
  Analyze Selected analyzes the latest run.
- Keys in the list: Enter analyzes the selection, Ctrl+A selects all,
  double-click analyzes that one session.
- Buttons: Analyze Selected, Select All, Select None, Refresh, Choose
  Files... (any CSV, several at once), Open Selected, Open TFL Folder.
- SESSION_LIST_ROWS (8): visible rows before the list scrolls.
- app.analysis_box: a 30-line Text widget below the list.

Edge cases
----------
- chronological_selection() hands the chosen files over oldest first,
  whatever order they were clicked in, so a pooled report lists sessions in
  the order they were run.
- An empty folder shows "No sessions yet" and Analyze Selected explains
  that nothing is selected instead of failing.
- Refresh selects only the newest session; it does not restore an earlier
  selection.
- The wheel scrolls the page when the list or report fits without
  scrolling (see bind_scroll_passthrough()).

Known limitations
-----------------
- The list shows saved dates and file names, not trial counts or labels;
  the analysis report shows those.
- A file deleted after the list was drawn shows an unavailable date, and
  analyzing it reports "Output file not found" for that file only.
- Plain-text report; no charts.
- Files outside the output folder are reached through Choose Files...,
  which analyzes them immediately and does not add them to the list.

Examples
--------
- app.show_page("Results"); app.analyze_tfl()
- chronological_selection([c, b, a], (0, 2))  # newest first in, [a, c] out
"""
from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import ttk

from frameworks.TFL.output import list_session_files
from gui.components.card import Card
from gui.components.page_helpers import bind_scroll_passthrough
from gui.theme import COLORS, FONT_MONO

SESSION_LIST_ROWS = 8


def chronological_selection(paths_newest_first: list, indices) -> list:
    """The chosen entries of a newest-first list, oldest first."""
    return [paths_newest_first[i] for i in sorted(indices, reverse=True)]


def session_label(path) -> str:
    try:
        saved = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    except OSError:
        return f"(date unavailable)   {path.name}"
    return f"{saved}   {path.name}"


def render(app):
    root = app.page_shell("Results", "Select one or more saved sessions, then analyze them.")
    card = Card(root)
    card.grid(row=2, column=0, sticky="ew", padx=26, pady=9)
    card.grid_columnconfigure(0, weight=1)
    ttk.Label(card, text="TFL Sessions", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(
        card,
        text=(f"Saved in: {app.tfl_output_dir()}\n"
              "Click a session, Ctrl+click to add more, or Shift+click for a range. "
              "Several sessions are pooled into one combined report."),
        style="CardMuted.TLabel", justify="left",
    ).grid(row=1, column=0, sticky="w", pady=(7, 8))

    list_frame = ttk.Frame(card, style="Card.TFrame")
    list_frame.grid(row=2, column=0, sticky="ew")
    list_frame.grid_columnconfigure(0, weight=1)
    session_list = tk.Listbox(
        list_frame, selectmode="extended", exportselection=False, height=SESSION_LIST_ROWS,
        bg=COLORS["panel2"], fg=COLORS["text"], selectbackground=COLORS["accent"],
        selectforeground=COLORS["on_accent"], relief="flat", font=FONT_MONO, activestyle="none",
        highlightthickness=0,
    )
    list_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=session_list.yview)
    session_list.configure(yscrollcommand=list_scroll.set)
    session_list.grid(row=0, column=0, sticky="ew")
    list_scroll.grid(row=0, column=1, sticky="ns")
    bind_scroll_passthrough(session_list, app)

    count_text = tk.StringVar(master=app, value="")
    ttk.Label(card, textvariable=count_text, style="CardMuted.TLabel").grid(row=3, column=0, sticky="w", pady=(6, 8))

    paths: list = []

    def chosen() -> list:
        return chronological_selection(paths, tuple(session_list.curselection() or ()))

    def update_count(_event=None) -> None:
        if not paths:
            count_text.set("No sessions yet. Run TFL first, or use Choose Files...")
        else:
            count_text.set(f"{len(tuple(session_list.curselection() or ()))} of {len(paths)} selected")

    def refresh() -> None:
        paths[:] = list(reversed(list_session_files(app.tfl_output_dir())))
        session_list.delete(0, "end")
        for path in paths:
            session_list.insert("end", session_label(path))
        if paths:
            session_list.selection_set(0)
        update_count()

    def select_all(_event=None):
        if paths:
            session_list.selection_set(0, "end")
        update_count()
        return "break"

    def select_none() -> None:
        session_list.selection_clear(0, "end")
        update_count()

    def analyze(_event=None):
        app.analyze_tfl(chosen())
        return "break"

    session_list.bind("<<ListboxSelect>>", update_count)
    session_list.bind("<Return>", analyze)
    session_list.bind("<Double-Button-1>", analyze)
    session_list.bind("<Control-a>", select_all)
    session_list.bind("<Control-A>", select_all)

    buttons = ttk.Frame(card, style="Card.TFrame")
    buttons.grid(row=4, column=0, sticky="w")
    for column, (label, command, primary) in enumerate((
        ("Analyze Selected", analyze, True),
        ("Select All", select_all, False),
        ("Select None", select_none, False),
        ("Refresh", refresh, False),
    )):
        ttk.Button(buttons, text=label, command=command,
                   style="Accent.TButton" if primary else "TButton").grid(row=0, column=column, padx=(0, 8))
    more = ttk.Frame(card, style="Card.TFrame")
    more.grid(row=5, column=0, sticky="w", pady=(8, 0))
    for column, (label, command) in enumerate((
        ("Choose Files...", app.choose_tfl_sessions),
        ("Open Selected", lambda: app.open_tfl_csvs(chosen())),
        ("Open TFL Folder", app.open_tfl_folder),
    )):
        ttk.Button(more, text=label, command=command).grid(row=0, column=column, padx=(0, 8))

    app.analysis_box = tk.Text(
        root, height=30, bg=COLORS["panel"], fg=COLORS["text"],
        insertbackground=COLORS["accent"], relief="flat", font=FONT_MONO, wrap="word",
    )
    app.analysis_box.grid(row=3, column=0, sticky="ew", padx=26, pady=10)
    app.analysis_box.insert("end", "No analysis yet. Select sessions above and choose Analyze Selected, "
                                   "or run TFL first.\n")
    bind_scroll_passthrough(app.analysis_box, app)
    refresh()
