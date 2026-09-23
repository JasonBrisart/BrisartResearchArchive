"""
Lightweight local .txt/.md document viewer, opened from the Archive
page. Read-only by design: this is for browsing README/notes/release
docs inside the GUI, not for editing them.
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
