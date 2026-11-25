r"""
File: brisart_ai/core/settings.py

Purpose
-------
Persist the file and note eligibility toggles.

The two persisted toggles control eligibility of imported files and research notes, not
the existence of records in the index. The old automatic web-research setting is
intentionally not part of the current runtime.

Public operations: ResearchSettings.load (self); ResearchSettings.save (self);
ResearchSettings.get (self, key); ResearchSettings.set (self, key, value).

Public operations: ResearchSettings.toggle (self, key); ResearchSettings.resolve_key
(self, raw_key); ResearchSettings.render (self).

Internal helpers include ResearchSettings.__init__.

Communication / relationships
-----------------------------
The service reads these options; the Tk settings dialog updates them. JSON is provided
by the external Native API.

Saving uses a temporary file in the destination directory followed by replacement. A
failed replacement restores the previous in-memory value so the GUI cannot claim a
preference was saved when it was not.

Direct project imports: brisart_ai, brisart_json.

Direct importing modules include brisart_ai/core/conversation.py,
brisart_ai/core/service.py, brisart_ai/core/tests/test_conversation.py,
brisart_ai/core/tests/test_service_headless.py, brisart_ai/core/tests/test_settings.py,
brisart_ai/ui/dialogs.py.

Concrete calls within this file include state.settings_path, self.load, self.set,
self.get, self.path.exists, self.save, self.values.get, self.path.read_text.

Settings / parameters
---------------------
search_local_files and search_notes default to True; a caller may supply a custom path.

Module configuration and named constants: DEFAULT_SETTINGS_PATH, DEFAULT_SETTINGS (dict,
2 entries), TOGGLE_LABELS (dict, 2 entries), SETTING_ALIASES (dict, 5 entries).

Call signatures: ResearchSettings.load(self); ResearchSettings.save(self);
ResearchSettings.get(self, key); ResearchSettings.set(self, key, value);
ResearchSettings.toggle(self, key).

Call signatures: ResearchSettings.resolve_key(self, raw_key);
ResearchSettings.render(self).

Edge cases
----------
Malformed or non-object JSON uses defaults. Failed atomic replacement rolls the changed
value back.

Missing, malformed, or non-object settings content falls back to the two defaults. This
does not provide a multi-process merge protocol.

Explicit exception branches or raised errors in this file include Exception, KeyError.

Known limitations
-----------------
Does not merge simultaneous writes from multiple app processes.

Examples
--------
settings.set("search_notes", False)

Other callable entry points in this module include ResearchSettings.save,
ResearchSettings.get, ResearchSettings.set, ResearchSettings.toggle,
ResearchSettings.resolve_key, ResearchSettings.render.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict

from brisart_ai import state
from brisart_json import brisart_dumps, brisart_loads

DEFAULT_SETTINGS_PATH = state.settings_path()
DEFAULT_SETTINGS: Dict[str, bool] = {
    "search_local_files": True,
    "search_notes": True,
}

TOGGLE_LABELS = {
    "search_local_files": "Local Files",
    "search_notes": "Research Notes",
}

SETTING_ALIASES = {
    "local": "search_local_files", "local-files": "search_local_files",
    "search_local_files": "search_local_files", "notes": "search_notes",
    "search_notes": "search_notes",
}


class ResearchSettings:
    """Loads, saves, and applies BrisartAI research toggles."""

    def __init__(self, path: Path = DEFAULT_SETTINGS_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.values: Dict[str, bool] = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.save()
            return
        try:
            data = brisart_loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        self.values = dict(DEFAULT_SETTINGS)
        if not isinstance(data, dict):
            return
        for key in DEFAULT_SETTINGS:
            if key in data and isinstance(data[key], bool):
                self.values[key] = data[key]

    def save(self) -> None:
        temporary = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(brisart_dumps(self.values, indent=2, sort_keys=True))
            temporary.replace(self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def get(self, key: str) -> bool:
        return bool(self.values.get(key, False))

    def set(self, key: str, value: bool) -> None:
        if key not in DEFAULT_SETTINGS:
            raise KeyError(f"Unknown setting: {key}")
        previous = self.values[key]
        self.values[key] = bool(value)
        try:
            self.save()
        except Exception:
            self.values[key] = previous
            raise

    def toggle(self, key: str) -> bool:
        new_value = not self.get(key)
        self.set(key, new_value)
        return new_value

    def resolve_key(self, raw_key: str) -> str:
        cleaned = str(raw_key or "").strip().lower()
        resolved = SETTING_ALIASES.get(cleaned)
        if not resolved:
            raise KeyError(f"Unknown setting '{raw_key}'. Try: local, notes")
        return resolved

    def render(self) -> str:
        lines = ["Research Sources", ""]
        for key, label in TOGGLE_LABELS.items():
            mark = "x" if self.get(key) else " "
            lines.append(f"[{mark}] {label}")
        lines.append("")
        if self.get("search_local_files"):
            lines.append(
                "Local Files is ON. Imported files are included in search."
            )
        else:
            lines.append(
                "Local Files is OFF. Imported files are ignored until "
                "this is turned back on."
            )
        lines.append("")
        if self.get("search_notes"):
            lines.append(
                "Research Notes is ON. Saved notes are merged into "
                "search results alongside imported files."
            )
        else:
            lines.append(
                "Research Notes is OFF. Saved notes exist in the vault "
                "but are not included in search results."
            )
        return "\n".join(lines)


__all__ = [
    "DEFAULT_SETTINGS", "DEFAULT_SETTINGS_PATH", "ResearchSettings",
    "SETTING_ALIASES", "TOGGLE_LABELS",
]
