"""
Interpretive classification logic for ReleaseNoteBuilder.
"""

from __future__ import annotations

import re


def contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def path_contains(path: str, keywords: list[str]) -> bool:
    lowered = path.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def classify_added_file(file_info: dict) -> str:
    path = file_info.get("path", "")
    text = file_info.get("text_preview", "")

    if path_contains(path, ["gui", "interface", "window"]):
        return "Added graphical interface support."
    if path_contains(path, ["readme", "docs", "documentation"]):
        return "Added or expanded project documentation."
    if path_contains(path, ["test", "tests"]):
        return "Added testing-related project files."
    if path_contains(path, ["config", "settings", "constants"]):
        return "Added configuration or settings support."
    if path_contains(path, ["manifest", "metadata"]):
        return "Added structured project metadata output."
    if path_contains(path, ["generator", "generators"]):
        return "Added generation logic for output artifacts."
    if path_contains(path, ["analysis", "analyzer", "scanner"]):
        return "Added project analysis logic."
    if path_contains(path, ["filesystem", "files", "path"]):
        return "Added filesystem handling support."
    if path.endswith(".py"):
        if contains_any(text, ["tkinter", "run_gui"]):
            return "Added GUI functionality."
        if contains_any(text, ["argparse", "sys.argv", "cli"]):
            return "Added command-line workflow support."
        return "Added a new Python module."
    if path.endswith(".md"):
        return "Added Markdown documentation."
    if path.endswith(".json"):
        return "Added structured JSON data."
    return f"Added `{path}`."


def classify_removed_file(file_info: dict) -> str:
    path = file_info.get("path", "")
    if path_contains(path, ["legacy", "old", "deprecated"]):
        return "Removed legacy or deprecated project logic."
    if path_contains(path, ["test", "tests"]):
        return "Removed testing-related files."
    if path_contains(path, ["readme", "docs", "documentation"]):
        return "Removed documentation files."
    return f"Removed `{path}`."


def classify_modified_file(change_info: dict) -> str:
    path = change_info.get("path", "")
    old_text = change_info.get("old", {}).get("text_preview", "")
    new_text = change_info.get("new", {}).get("text_preview", "")
    combined = f"{old_text}\n{new_text}"

    if path_contains(path, ["readme", "docs", "documentation"]):
        return "Updated project documentation."
    if path_contains(path, ["gui", "interface", "window"]):
        return "Updated graphical interface behavior."
    if path_contains(path, ["generator", "generators"]):
        return "Updated output generation logic."
    if path_contains(path, ["analysis", "analyzer", "scanner"]):
        return "Updated project analysis logic."
    if path_contains(path, ["filesystem", "files", "path"]):
        return "Updated filesystem handling."
    if path_contains(path, ["constants", "settings", "config"]):
        return "Updated configuration or constants."
    if path_contains(path, ["manifest", "metadata"]):
        return "Updated structured metadata handling."
    if contains_any(combined, ["tkinter", "run_gui"]):
        return "Improved GUI-related functionality."
    if contains_any(combined, ["argparse", "sys.argv", "command-line", "cli"]):
        return "Improved command-line workflow support."
    if contains_any(combined, ["json", "manifest"]):
        return "Improved structured metadata generation."
    if contains_any(combined, ["hashlib", "sha256", "snapshot"]):
        return "Improved snapshot or file comparison logic."
    if path.endswith(".py"):
        return "Updated Python project logic."
    if path.endswith(".md"):
        return "Updated Markdown documentation."
    if path.endswith(".json"):
        return "Updated structured JSON data."
    return f"Updated `{path}`."


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    output = []
    for item in items:
        normalized = re.sub(r"\s+", " ", item.strip().lower())
        if normalized not in seen:
            seen.add(normalized)
            output.append(item)
    return output


def classify_release_changes(diff: dict) -> dict:
    added = [classify_added_file(info) for info in diff.get("added", [])]
    removed = [classify_removed_file(info) for info in diff.get("removed", [])]
    modified = [classify_modified_file(info) for info in diff.get("modified", [])]
    return {
        "added": dedupe_preserve_order(added),
        "changed": dedupe_preserve_order(modified),
        "removed": dedupe_preserve_order(removed),
    }


def summarize_release_type(classified: dict, diff: dict) -> str:
    added_count = len(diff.get("added", []))
    modified_count = len(diff.get("modified", []))
    removed_count = len(diff.get("removed", []))
    added_text = " ".join(classified.get("added", [])).lower()
    changed_text = " ".join(classified.get("changed", [])).lower()
    removed_text = " ".join(classified.get("removed", [])).lower()
    combined_text = f"{added_text} {changed_text} {removed_text}"

    if "graphical" in combined_text or "gui" in combined_text:
        return "Feature release with interface-related functionality."
    if "documentation" in combined_text or "markdown" in combined_text:
        return "Documentation-focused release."
    if "metadata" in combined_text or "manifest" in combined_text:
        return "Metadata and tooling release."
    if "command-line" in combined_text or "cli" in combined_text:
        return "Workflow and command-line improvement release."
    if added_count > modified_count and added_count >= 3:
        return "Feature expansion release."
    if modified_count > 0 and added_count == 0 and removed_count == 0:
        return "Maintenance and improvement release."
    if removed_count > 0:
        return "Cleanup and restructuring release."
    if added_count == 0 and modified_count == 0 and removed_count == 0:
        return "No file changes detected."
    return "General project update."
