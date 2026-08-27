"""
config/tooling_catalog.py
Static catalog of every Brisart-family program the Archive's Tooling
page can download, run, and keep version-tracked -- the Tooling
equivalent of config/registries.py's RESERVED_FRAMEWORKS list, except
these are separate, independently-installed programs rather than
in-process frameworks.

Talks to:
  - gui/pages/tooling_page.py reads TOOLING_CATALOG to render one card
    per program.
  - services/tooling_manager.py reads it to know each program's
    registry ID (for fetching its update entry) and expected
    executable path once installed.
  - Nothing in this file ever contacts the network or the filesystem
    -- it is pure static data, safe to import from anywhere.

Each catalog entry is a dict with these keys:
  - "id": the app ID this program is published under in the shared
    registry page (services/updater/registry.py's
    fetch_registry_entry(app_id=...) call uses this exact string as
    the JSON key to look up on brisartresearcharchive.com's registry
    page). MUST exactly match whatever key Jason publishes for that
    program when signing a release with signing/sign_release.py --
    a mismatch here means that program's update check will always
    fail with a RegistryError ("no entry found"), not silently pick
    the wrong entry.
  - "name": human-readable display name shown on the Tooling page.
  - "description": one or two sentences of card body text.
  - "executable": the relative path, from the program's own install
    folder root, to the file that should be launched by "Run" (e.g.
    "BrisartIdentityTools.exe" for a compiled Windows app, or
    "main.py" for a program meant to be run via python). This is
    REQUIRED to be correct for "Run" to work -- if a program's real
    entry point differs from this value, update this catalog entry,
    not tooling_manager.py's launch logic.
  - "asset_kind_hint": "zip" or "exe" -- purely informational default
    for this catalog entry; the AUTHORITATIVE asset kind for any given
    download always comes from that program's own registry entry
    (RegistryEntry.asset_kind, set when the release was signed), never
    from this hint. Kept here only so the Tooling page can show a
    reasonable placeholder ("Installs as: .zip") before any registry
    check has actually run yet.

IMPORTANT: Adding a program to this list does NOT publish it anywhere
and does NOT require a corresponding registry entry to exist yet -- an
entry with no matching registry page entry simply shows "Download"
and, if clicked, fails gracefully with a clear RegistryError message
(see services/tooling_manager.py), exactly like any other network
failure elsewhere in this app.
"""
from __future__ import annotations

TOOLING_CATALOG: list[dict] = [
    {
        "id": "brisart_identity_tools",
        "name": "BrisartIdentityTools",
        "description": (
            "Encrypt and decrypt arbitrary files, folders, and drives, "
            "with biometric-backed vault storage and a GUI on top of a "
            "CLI-friendly core."
        ),
        "executable": "BrisartIdentityTools.exe",
        "asset_kind_hint": "zip",
    },
    {
        "id": "brisart_ai",
        "name": "BrisartAI",
        "description": (
            "Lightweight, locally-controlled knowledge/search/ranking "
            "assistant with note participation and a sequential web "
            "search fallback."
        ),
        "executable": "BrisartAI.exe",
        "asset_kind_hint": "zip",
    },
    {
        "id": "brisart_os",
        "name": "BrisartOS",
        "description": (
            "Pure Python, fully custom-made operating system project, "
            "including bootloader and bare-metal verification tooling."
        ),
        "executable": "BrisartOS.exe",
        "asset_kind_hint": "zip",
    },
    {
        "id": "project_context_helper",
        "name": "Project Context Helper",
        "description": (
            "Generates and maintains project-context exports so tools "
            "and assistants can reason about a codebase without manual "
            "re-explaining."
        ),
        "executable": "ProjectContextHelper.exe",
        "asset_kind_hint": "zip",
    },
    {
        "id": "entitle",
        "name": "Entitle",
        "description": "Utility tool in the Brisart ecosystem.",
        "executable": "Entitle.exe",
        "asset_kind_hint": "exe",
    },
    {
        "id": "autoexebuilder",
        "name": "AutoExeBuilder",
        "description": (
            "Builds standalone executables from Brisart Python projects "
            "for distribution without requiring a Python install."
        ),
        "executable": "AutoExeBuilder.exe",
        "asset_kind_hint": "exe",
    },
]


def get_catalog_entry(tool_id: str) -> dict | None:
    """Returns the catalog dict for `tool_id`, or None if it isn't a
    known program. Safe to call with any string, including ones that
    don't exist yet -- e.g. a value that was previously installed but
    has since been removed from TOOLING_CATALOG."""
    for entry in TOOLING_CATALOG:
        if entry.get("id") == tool_id:
            return entry
    return None


__all__ = ["TOOLING_CATALOG", "get_catalog_entry"]
