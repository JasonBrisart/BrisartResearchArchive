"""
File: gui/components/document_viewer.py

Purpose
-------
Open a local .txt or .md document in a read-only viewer window from the
Archive page.

Communication / relationships
-----------------------------
- open_local_doc(app) is called through SystemController.open_local_doc(),
  wired to the Archive page button.
- Uses COLORS and FONT_MONO from gui/theme.py.

Settings / parameters
---------------------
- ALLOWED_SUFFIXES: .txt and .md.
- MAX_DOCUMENT_BYTES: 5,000,000.
- The file dialog starts in app.execution_dir; the viewer opens at 900x680
  with the file's full path above the text.

Edge cases
----------
- Cancelling the file dialog does nothing.
- An unsupported suffix, an oversized file, or a file that cannot be read
  or decoded shows an error dialog and opens no window.
- UTF-8 files with a byte-order mark are accepted.
- Each call opens a new window; nothing limits how many.

Known limitations
-----------------
- Markdown is shown as raw text, not rendered.
- Files that are not UTF-8 are rejected.
- The text box has no scrollbar; it scrolls with the mouse wheel or the
  keyboard.
- The text is read-only (the widget is disabled); there is no search.

Examples
--------
- open_local_doc(app)
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from gui.theme import COLORS, FONT_MONO

ALLOWED_SUFFIXES = {".txt", ".md"}
MAX_DOCUMENT_BYTES = 5_000_000


def open_local_doc(app) -> None:
    initial_directory = str(getattr(app, "execution_dir", Path.cwd()))
    selected_path = filedialog.askopenfilename(
        title="Open Archive Document",
        initialdir=initial_directory,
        filetypes=[("Text and Markdown", "*.txt *.md"), ("All files", "*.*")],
        parent=app,
    )
    if not selected_path:
        return
    path = Path(selected_path)
    if path.suffix.casefold() not in ALLOWED_SUFFIXES:
        messagebox.showerror("Unsupported File", "Only .txt and .md files can be opened here.", parent=app)
        return
    try:
        if path.stat().st_size > MAX_DOCUMENT_BYTES:
            raise ValueError("The selected document is too large to preview here.")
        content = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        messagebox.showerror("Could Not Open Document", f"{type(exc).__name__}: {exc}", parent=app)
        return

    viewer = tk.Toplevel(app)
    viewer.title(f"Archive Document — {path.name}")
    viewer.geometry("900x680")
    viewer.configure(bg=COLORS["bg"])

    frame = ttk.Frame(viewer, style="Bg.TFrame", padding=16)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=str(path), style="Muted.TLabel", wraplength=860).pack(anchor="w", pady=(0, 10))

    text_box = tk.Text(
        frame, bg=COLORS["panel"], fg=COLORS["text"], insertbackground=COLORS["accent"],
        relief="flat", font=FONT_MONO, wrap="word",
    )
    text_box.pack(fill="both", expand=True)
    text_box.insert("1.0", content)
    text_box.configure(state="disabled")


__all__ = ["open_local_doc"]


