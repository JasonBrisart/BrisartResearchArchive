#!/usr/bin/env python3
"""
canonsync_gui.py
----------------
Tkinter GUI for CanonSync.

Point it at a parent folder (e.g. your GitHub directory). It discovers
every git repo inside, lets you choose which canonical files to sync and
which repos are allowed, previews exactly what would change per repo and
per file, and writes on Apply.

- Canonical files: tick the ones you want to sync.
- Repositories: tick = ALLOW (gets written), untick = BLOCK (skipped).
- "block" files keep each repo's own rules around the managed block.
- "whole" files (LICENSE) are full replacements and are disabled by
  default in canonsync.config.json.
- Optionally writes a timestamped ".bak" before overwriting anything.

Pure standard library (tkinter). Local-first. Nothing is written until you
press Apply, and Apply asks for confirmation first.

Run:  python canonsync_gui.py
"""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import canonsync_core as core

DEFAULT_CONFIG = "canonsync.config.json"

CHECK_ON = "\u2611"   # ☑
CHECK_OFF = "\u2610"  # ☐

STATUS_LABEL = {
    core.STATUS_CREATE: "CREATE",
    core.STATUS_UPDATE: "UPDATE",
    core.STATUS_UNCHANGED: "unchanged",
    core.STATUS_MISSING: "MISSING",
    core.STATUS_SKIPPED: "BLOCKED",
}

STATUS_COLOR = {
    core.STATUS_CREATE: "#0a7d28",
    core.STATUS_UPDATE: "#b35c00",
    core.STATUS_UNCHANGED: "#666666",
    core.STATUS_MISSING: "#b00020",
    core.STATUS_SKIPPED: "#8a6d00",
}


class CanonSyncApp(tk.Tk):
    """
    Main application window.
    """

    def __init__(self) -> None:
        super().__init__()
        self.title(f"{core.APP_NAME} v{core.APP_VERSION}")
        self.geometry("920x720")
        self.minsize(780, 600)

        self.config_path = tk.StringVar(value=str(Path(DEFAULT_CONFIG).resolve()))
        self.parent_dir = tk.StringVar(value="")
        self.backup_var = tk.BooleanVar(value=False)
        self.repos: list[Path] = []
        self.repo_allow: dict[str, bool] = {}  # str(repo) -> allowed?
        self.last_results: list[dict] = []
        self.item_vars: dict[str, tk.BooleanVar] = {}
        self.config_data: dict = {}

        self._build_widgets()
        self._load_config_items()

    # -- layout -----------------------------------------------------------
    def _build_widgets(self) -> None:
        pad = {"padx": 8, "pady": 4}

        cfg = ttk.LabelFrame(self, text="Canon config")
        cfg.pack(fill="x", **pad)
        ttk.Entry(cfg, textvariable=self.config_path).pack(
            side="left", fill="x", expand=True, padx=6, pady=6
        )
        ttk.Button(cfg, text="Browse…", command=self._pick_config).pack(side="left", padx=3, pady=6)
        ttk.Button(cfg, text="Reload", command=self._load_config_items).pack(side="left", padx=3, pady=6)

        self.items_frame = ttk.LabelFrame(self, text="Canonical files to sync (checked = included)")
        self.items_frame.pack(fill="x", **pad)

        mid = ttk.LabelFrame(self, text="Repositories folder")
        mid.pack(fill="x", **pad)
        ttk.Entry(mid, textvariable=self.parent_dir).pack(
            side="left", fill="x", expand=True, padx=6, pady=6
        )
        ttk.Button(mid, text="Browse…", command=self._pick_parent).pack(side="left", padx=3, pady=6)
        ttk.Button(mid, text="Scan", command=self._scan).pack(side="left", padx=3, pady=6)

        # -- checkable repo list --
        repo_frame = ttk.LabelFrame(
            self, text="Repositories  (checked = ALLOW / write · unchecked = BLOCK / skip)"
        )
        repo_frame.pack(fill="both", expand=True, **pad)

        repo_bar = ttk.Frame(repo_frame)
        repo_bar.pack(fill="x", padx=6, pady=(6, 0))
        ttk.Button(repo_bar, text="Allow all", command=lambda: self._set_all_repos(True)).pack(side="left")
        ttk.Button(repo_bar, text="Block all", command=lambda: self._set_all_repos(False)).pack(side="left", padx=4)
        self.repo_count_var = tk.StringVar(value="No repos scanned yet.")
        ttk.Label(repo_bar, textvariable=self.repo_count_var).pack(side="right")

        self.repo_tree = ttk.Treeview(
            repo_frame, columns=("allow", "repo"), show="headings", height=6
        )
        self.repo_tree.heading("allow", text="Allow")
        self.repo_tree.heading("repo", text="Repository")
        self.repo_tree.column("allow", width=70, anchor="center", stretch=False)
        self.repo_tree.column("repo", width=760, anchor="w")
        self.repo_tree.tag_configure("blocked", foreground="#8a6d00")
        self.repo_tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        self.repo_tree.bind("<Button-1>", self._on_repo_click)
        self.repo_tree.bind("<space>", self._on_repo_space)

        repo_scroll = ttk.Scrollbar(repo_frame, orient="vertical", command=self.repo_tree.yview)
        repo_scroll.pack(side="left", fill="y", pady=6)
        self.repo_tree.configure(yscrollcommand=repo_scroll.set)

        # -- plan table --
        table = ttk.LabelFrame(self, text="Plan")
        table.pack(fill="both", expand=True, **pad)

        columns = ("status", "item", "repo")
        self.tree = ttk.Treeview(table, columns=columns, show="headings", height=10)
        self.tree.heading("status", text="Action")
        self.tree.heading("item", text="File")
        self.tree.heading("repo", text="Repository")
        self.tree.column("status", width=100, anchor="w", stretch=False)
        self.tree.column("item", width=130, anchor="w", stretch=False)
        self.tree.column("repo", width=620, anchor="w")
        for status, color in STATUS_COLOR.items():
            self.tree.tag_configure(status, foreground=color)
        self.tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)

        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        scroll.pack(side="left", fill="y", pady=6)
        self.tree.configure(yscrollcommand=scroll.set)

        actions = ttk.Frame(self)
        actions.pack(fill="x", **pad)
        ttk.Button(actions, text="Preview (dry run)", command=self._preview).pack(side="left", padx=6)
        self.apply_btn = ttk.Button(actions, text="Apply", command=self._apply, state="disabled")
        self.apply_btn.pack(side="left", padx=6)
        ttk.Checkbutton(
            actions, text="Back up files before overwriting", variable=self.backup_var
        ).pack(side="left", padx=12)
        ttk.Button(actions, text="Quit", command=self.destroy).pack(side="right", padx=6)

        self.status_var = tk.StringVar(value="Load a config, pick a repos folder, then Scan.")
        ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w").pack(
            fill="x", side="bottom"
        )

    # -- config / items ---------------------------------------------------
    def _pick_config(self) -> None:
        path = filedialog.askopenfilename(
            title="Select canonsync.config.json", initialfile=DEFAULT_CONFIG
        )
        if path:
            self.config_path.set(path)
            self._load_config_items()

    def _load_config_items(self) -> None:
        for child in self.items_frame.winfo_children():
            child.destroy()
        self.item_vars.clear()

        cfg_path = Path(self.config_path.get()).expanduser().resolve()
        try:
            self.config_data = core.load_config(cfg_path)
        except Exception as exc:
            messagebox.showerror(core.APP_NAME, f"Could not load config:\n{exc}")
            return

        for item in self.config_data.get("items", []):
            var = tk.BooleanVar(value=bool(item.get("enabled", True)))
            self.item_vars[item["name"]] = var
            text = f"{item['name']}  →  {item['dest']}  [{item.get('mode', 'block')}]"
            ttk.Checkbutton(self.items_frame, text=text, variable=var).pack(
                anchor="w", padx=8, pady=1
            )
        self.status_var.set(
            f"Loaded {len(self.item_vars)} canonical file(s). Pick a repos folder and Scan."
        )

    def _selected_items(self) -> set[str]:
        return {name for name, var in self.item_vars.items() if var.get()}

    # -- repo allow/block -------------------------------------------------
    def _repo_of_row(self, row: str) -> str:
        return self.repo_tree.item(row, "values")[1]

    def _render_repo_row(self, row: str) -> None:
        repo = self._repo_of_row(row)
        allowed = self.repo_allow.get(repo, True)
        glyph = CHECK_ON if allowed else CHECK_OFF
        self.repo_tree.item(
            row, values=(glyph, repo), tags=() if allowed else ("blocked",)
        )

    def _toggle_repo(self, row: str) -> None:
        repo = self._repo_of_row(row)
        self.repo_allow[repo] = not self.repo_allow.get(repo, True)
        self._render_repo_row(row)
        self._update_repo_count()

    def _on_repo_click(self, event) -> None:
        if self.repo_tree.identify_region(event.x, event.y) != "cell":
            return
        col = self.repo_tree.identify_column(event.x)
        row = self.repo_tree.identify_row(event.y)
        if not row:
            return
        if col == "#1":  # only the Allow column toggles
            self._toggle_repo(row)
            return "break"

    def _on_repo_space(self, event) -> None:
        row = self.repo_tree.focus()
        if row:
            self._toggle_repo(row)
            return "break"

    def _set_all_repos(self, allowed: bool) -> None:
        for row in self.repo_tree.get_children():
            repo = self._repo_of_row(row)
            self.repo_allow[repo] = allowed
            self._render_repo_row(row)
        self._update_repo_count()

    def _update_repo_count(self) -> None:
        total = len(self.repos)
        allowed = sum(1 for r in self.repos if self.repo_allow.get(str(r), True))
        self.repo_count_var.set(f"{allowed} allowed / {total - allowed} blocked / {total} total")

    def _blocked_set(self) -> set[Path]:
        return {r for r in self.repos if not self.repo_allow.get(str(r), True)}

    def _allowed_repos(self) -> list[Path]:
        return [r for r in self.repos if self.repo_allow.get(str(r), True)]

    # -- helpers ----------------------------------------------------------
    def _pick_parent(self) -> None:
        path = filedialog.askdirectory(title="Select the folder containing your repos")
        if path:
            self.parent_dir.set(path)

    def _clear_table(self) -> None:
        for row in self.tree.get_children():
            self.tree.delete(row)

    def _fill_table(self, results: list[dict]) -> None:
        self._clear_table()
        for r in results:
            status = r["status"]
            self.tree.insert(
                "",
                "end",
                values=(STATUS_LABEL[status], r["item"], str(r["repo"])),
                tags=(status,),
            )

    def _scan(self) -> None:
        parent = self.parent_dir.get().strip()
        if not parent:
            messagebox.showwarning(core.APP_NAME, "Choose a repositories folder first.")
            return
        root = Path(parent).expanduser().resolve()
        if not root.exists():
            messagebox.showerror(core.APP_NAME, f"Folder does not exist:\n{root}")
            return

        self.repos = core.discover_repos(root)
        self._clear_table()
        for row in self.repo_tree.get_children():
            self.repo_tree.delete(row)
        self.repo_allow.clear()
        self.apply_btn.configure(state="disabled")

        if not self.repos:
            self.repo_count_var.set("No repos found.")
            self.status_var.set("No git repos found in that folder.")
            messagebox.showinfo(core.APP_NAME, "No git repositories found (no .git in immediate subfolders).")
            return

        for repo in self.repos:
            key = str(repo)
            self.repo_allow[key] = True  # default: allow
            self.repo_tree.insert("", "end", values=(CHECK_ON, key))
        self._update_repo_count()
        self.status_var.set(f"Found {len(self.repos)} repo(s). Allow/block as needed, then Preview.")

    def _run(self, apply: bool) -> None:
        if not self.repos:
            messagebox.showwarning(core.APP_NAME, "Scan for repos first.")
            return
        only = self._selected_items()
        if not only:
            messagebox.showwarning(core.APP_NAME, "Select at least one canonical file to sync.")
            return
        if not self._allowed_repos():
            messagebox.showwarning(core.APP_NAME, "Every repo is blocked. Allow at least one.")
            return

        try:
            results = core.sync(
                self.config_data,
                self.repos,
                apply=apply,
                only=only,
                backup=self.backup_var.get(),
                blocked=self._blocked_set(),
            )
        except Exception as exc:
            messagebox.showerror(core.APP_NAME, f"Sync failed:\n{exc}")
            return

        self.last_results = results
        self._fill_table(results)

        c = core.summarize(results)
        verb = "Wrote" if apply else "Would change"
        self.status_var.set(
            f"{verb}: {c[core.STATUS_CREATE]} create, {c[core.STATUS_UPDATE]} update, "
            f"{c[core.STATUS_UNCHANGED]} unchanged, {c[core.STATUS_MISSING]} missing, "
            f"{c[core.STATUS_SKIPPED]} blocked."
        )
        has_changes = (c[core.STATUS_CREATE] + c[core.STATUS_UPDATE]) > 0
        self.apply_btn.configure(state=("normal" if (has_changes and not apply) else "disabled"))

        if apply:
            backed_up = sum(1 for r in results if r.get("backup"))
            extra = f" ({backed_up} backup file(s) written)" if backed_up else ""
            messagebox.showinfo(core.APP_NAME, f"Done. Changes written.{extra}")

    def _preview(self) -> None:
        self._run(apply=False)

    def _apply(self) -> None:
        c = core.summarize(self.last_results) if self.last_results else None
        if not c or (c[core.STATUS_CREATE] + c[core.STATUS_UPDATE]) == 0:
            messagebox.showinfo(core.APP_NAME, "Nothing to apply. Preview first.")
            return

        whole_selected = [
            i["name"]
            for i in core.enabled_items(self.config_data, only=self._selected_items())
            if i.get("mode") == core.MODE_WHOLE
        ]
        warn = ""
        if whole_selected:
            warn = (
                f"\n\nNOTE: {', '.join(whole_selected)} use WHOLE mode and will "
                "REPLACE the entire destination file in each repo."
            )
        blocked = self._blocked_set()
        if blocked:
            warn += f"\n\n{len(blocked)} repo(s) are blocked and will be skipped."
        if self.backup_var.get():
            warn += "\n\nBackups: a timestamped .bak will be written before each overwrite."

        if not messagebox.askyesno(
            core.APP_NAME,
            f"Write {(c[core.STATUS_CREATE] + c[core.STATUS_UPDATE])} change(s) "
            f"across the allowed repos?{warn}",
        ):
            return
        self._run(apply=True)


def main() -> None:
    CanonSyncApp().mainloop()


if __name__ == "__main__":
    main()
