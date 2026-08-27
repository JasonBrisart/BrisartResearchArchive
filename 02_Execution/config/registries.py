"""
Framework discovery and page registry.
Kept from the Archive branch, which already isolated framework
discovery failures so one malformed plugin can't take down the whole
app - that isolation behavior is exactly what the merge keeps.
"""
from __future__ import annotations

import importlib
import traceback
from pathlib import Path
from types import ModuleType
from typing import Any

# ============================================================
# Constants
# ============================================================

# __file__ is <EXECUTION_DIR>/config/registries.py, so parents[0] is the
# config/ folder and parents[1] is the execution root itself. (The
# previous version of this file additionally did `.parent` here, which
# pointed one directory too high and silently made framework discovery
# find zero frameworks - fixed now.)
EXECUTION_DIR = Path(__file__).resolve().parents[1]
FRAMEWORKS_DIR = EXECUTION_DIR / "frameworks"

RESERVED_FRAMEWORKS = [
    {"id": "SST", "name": "Simulation Synchronization Theory",
     "status": "Coming Soon", "module": "", "runner_module": "",
     "runner_class": "", "description": "Reserved framework slot.", "features": []},
    {"id": "IRE", "name": "Intent Resolution Engine",
     "status": "Coming Soon", "module": "", "runner_module": "",
     "runner_class": "", "description": "Reserved framework slot.", "features": []},
    {"id": "PFT", "name": "Perceptual Framing Theory",
     "status": "Coming Soon", "module": "", "runner_module": "",
     "runner_class": "", "description": "Reserved framework slot.", "features": []},
    {"id": "PCT", "name": "Predictive Convergence Theory",
     "status": "Coming Soon", "module": "", "runner_module": "",
     "runner_class": "", "description": "Reserved framework slot.", "features": []},
    {"id": "RIET", "name": "Residual Identity Echo Theory",
     "status": "Coming Soon", "module": "", "runner_module": "",
     "runner_class": "", "description": "Reserved framework slot.", "features": []},
]

FRAMEWORK_DISPLAY_ORDER = ["TFL", "SST", "IRE", "PFT", "PCT", "RIET"]

REQUIRED_METADATA_KEYS = [
    "id", "name", "status", "module",
    "runner_module", "runner_class", "description", "features",
]

# ============================================================
# Shared mutable state
# ============================================================

DISCOVERY_ERRORS: list[dict[str, str]] = []
FRAMEWORK_REGISTRY: list[dict] = []

# ============================================================
# Page registry
# ============================================================

# gui.pages is imported lazily (not at module load time) so that
# config.registries - and therefore framework discovery - can be
# imported and unit-tested in headless/no-display environments without
# ever touching Tkinter. Only actually rendering a page requires a
# display.

# NOTE: The canonical name for the settings/config page is "Settings"
# (not "System" - that was the old pre-rename name). "System" is kept
# here only as a backward-compatible alias in case anything external
# still references it.
PAGE_ALIASES = {
    "Home": "Dashboard",
    "Execution": "Frameworks",
    "Analysis": "Results",
    "Documentation": "Archive",
    "System": "Settings",
}

# Main navigation group, rendered top-down in the sidebar. Tooling and
# Settings are DELIBERATELY NOT part of this list -- both are rendered
# as their own bottom-pinned section by gui.components.sidebar.build_sidebar
# (see TOOLING_NAV_ITEM / SETTINGS_NAV_ITEM below), separated from this
# main list by an expanding spacer and a divider, since both are
# app-level/utility pages rather than primary content pages like the
# four below.
NAV_ITEMS = [
    ("Dashboard", "\u2302"),
    ("Frameworks", "\U0001F9EA"),
    ("Results", "\U0001F4CA"),
    ("Archive", "\U0001F4DA"),
]

# Bottom-pinned section, rendered in THIS order -- Tooling directly
# above Settings, both below the divider. Kept as two separate named
# constants (rather than one list) so gui/components/sidebar.py's
# build_sidebar() can bind each one to its own distinct pack() call
# with predictable, explicit stacking order, instead of looping over
# an ordered list where the visual order would depend on iteration
# order matching pack()'s bottom-up stacking behavior implicitly.
TOOLING_NAV_ITEM = ("Tooling", "\U0001F6E0")
SETTINGS_NAV_ITEM = ("Settings", "\u2699")

DEFAULT_PAGE = "Dashboard"

_PAGE_REGISTRY_CACHE: dict | None = None


def normalize_page_name(name: str) -> str:
    return PAGE_ALIASES.get(name, name)


def get_page_registry() -> dict:
    """
    Build (once) and return the page-name -> render-function mapping.
    Imports gui.pages on first call only, so this stays untouched by
    any test that never needs to render a page.

    NOTE: "Settings" resolves to gui.pages.settings_page.render (the
    checkbox-based settings/config page, matching the <name>_page.py
    naming convention used by every other page module, and matching
    its displayed title). The old "System" name/file has been fully
    replaced; "System" now only survives as an alias in PAGE_ALIASES
    for backward compatibility.

    "Tooling" resolves to gui.pages.tooling_page.render -- the page
    listing every downloadable Brisart-family program (see
    config/tooling_catalog.py). Its sidebar position is governed by
    TOOLING_NAV_ITEM above, not NAV_ITEMS -- this mapping only cares
    about page NAMES, not where each name appears in the sidebar.
    """
    global _PAGE_REGISTRY_CACHE
    if _PAGE_REGISTRY_CACHE is None:
        from gui.pages import archive_page, dashboard_page, frameworks_page, results_page, settings_page, tooling_page
        _PAGE_REGISTRY_CACHE = {
            "Dashboard": dashboard_page.render,
            "Frameworks": frameworks_page.render,
            "Results": results_page.render,
            "Archive": archive_page.render,
            "Settings": settings_page.render,
            "Tooling": tooling_page.render,
        }
    return _PAGE_REGISTRY_CACHE


def get_page_renderer(name: str):
    return get_page_registry().get(normalize_page_name(name))


# ============================================================
# Diagnostics
# ============================================================

def clear_discovery_errors() -> None:
    DISCOVERY_ERRORS.clear()


def record_discovery_error(module_name: str, exc: BaseException) -> None:
    error = {
        "module": str(module_name),
        "error_type": type(exc).__name__,
        "message": str(exc),
        "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    }
    DISCOVERY_ERRORS.append(error)
    print(f"Framework discovery skipped {module_name}: {error['error_type']}: {error['message']}")


def get_discovery_errors() -> list[dict[str, str]]:
    return [dict(error) for error in DISCOVERY_ERRORS]


# ============================================================
# Metadata normalization
# ============================================================

def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_features(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple, set)):
        value = [value]
    features = []
    for item in value:
        text = normalize_text(item)
        if text:
            features.append(text)
    return features


def normalize_metadata(metadata: dict) -> dict:
    if not isinstance(metadata, dict):
        raise TypeError("Framework metadata must be a dictionary.")
    clean = dict(metadata)
    for key in REQUIRED_METADATA_KEYS:
        if key not in clean:
            clean[key] = [] if key == "features" else ""
    for key in ("id", "name", "status", "module", "runner_module", "runner_class", "description"):
        clean[key] = normalize_text(clean[key])
    clean["features"] = normalize_features(clean["features"])
    return clean


def is_valid_metadata(metadata: Any) -> bool:
    if not isinstance(metadata, dict):
        return False
    framework_id = normalize_text(metadata.get("id", ""))
    framework_name = normalize_text(metadata.get("name", ""))
    return bool(framework_id and framework_name)


# ============================================================
# Discovery
# ============================================================

def is_discoverable_framework_directory(path: Path) -> bool:
    if not path.is_dir():
        return False
    name = path.name
    if name.startswith(".") or name.startswith("_"):
        return False
    if name.casefold() == "shared":
        return False
    return (path / "framework.py").is_file()


def discover_framework_module_names() -> list[str]:
    if not FRAMEWORKS_DIR.exists() or not FRAMEWORKS_DIR.is_dir():
        return []
    module_names = []
    try:
        paths = list(FRAMEWORKS_DIR.iterdir())
    except OSError as exc:
        record_discovery_error(str(FRAMEWORKS_DIR), exc)
        return []
    for path in paths:
        try:
            discoverable = is_discoverable_framework_directory(path)
        except OSError as exc:
            record_discovery_error(str(path), exc)
            continue
        if discoverable:
            module_names.append(f"frameworks.{path.name}.framework")
    return sorted(module_names, key=str.casefold)


def import_framework_module(module_name: str) -> ModuleType | None:
    try:
        return importlib.import_module(module_name)
    except Exception as exc:
        record_discovery_error(module_name, exc)
        return None


def extract_framework_metadata(module_name: str, module: ModuleType) -> dict | None:
    metadata = getattr(module, "FRAMEWORK_METADATA", None)
    if metadata is None:
        record_discovery_error(module_name, AttributeError("FRAMEWORK_METADATA not found"))
        return None
    if not is_valid_metadata(metadata):
        record_discovery_error(module_name, ValueError("FRAMEWORK_METADATA is invalid"))
        return None
    try:
        normalized = normalize_metadata(metadata)
    except Exception as exc:
        record_discovery_error(module_name, exc)
        return None
    if not normalized["module"]:
        normalized["module"] = module_name
    return normalized


def discover_frameworks() -> list:
    clear_discovery_errors()
    importlib.invalidate_caches()
    discovered = []
    discovered_ids = set()
    for module_name in discover_framework_module_names():
        module = import_framework_module(module_name)
        if module is None:
            continue
        metadata = extract_framework_metadata(module_name, module)
        if metadata is None:
            continue
        framework_id = metadata["id"]
        if framework_id in discovered_ids:
            record_discovery_error(module_name, ValueError(f"Duplicate framework ID: {framework_id}"))
            continue
        discovered_ids.add(framework_id)
        discovered.append(metadata)
    return discovered


# ============================================================
# Registry build / sort / lookups
# ============================================================

def sort_frameworks(frameworks: list[dict]) -> list:
    order_lookup = {fid: index for index, fid in enumerate(FRAMEWORK_DISPLAY_ORDER)}

    def sort_key(framework: dict) -> tuple[int, str]:
        framework_id = normalize_text(framework.get("id", ""))
        return (order_lookup.get(framework_id, 999), framework_id.casefold())

    return sorted(frameworks, key=sort_key)


def build_framework_registry() -> list[dict]:
    registry = []
    discovered = discover_frameworks()
    discovered_ids = {f["id"] for f in discovered}
    registry.extend(discovered)
    for reserved in RESERVED_FRAMEWORKS:
        try:
            reserved_metadata = normalize_metadata(reserved)
        except Exception as exc:
            record_discovery_error("RESERVED_FRAMEWORKS", exc)
            continue
        if reserved_metadata["id"] not in discovered_ids:
            registry.append(reserved_metadata)
    return sort_frameworks(registry)


def framework_id_matches(left: str, right: str) -> bool:
    return normalize_text(left).casefold() == normalize_text(right).casefold()


def get_framework(framework_id: str) -> dict | None:
    requested_id = normalize_text(framework_id)
    if not requested_id:
        return None
    for item in FRAMEWORK_REGISTRY:
        if framework_id_matches(item.get("id", ""), requested_id):
            return item
    return None


def get_available_frameworks() -> list[dict]:
    return [f for f in FRAMEWORK_REGISTRY if normalize_text(f.get("status", "")).casefold() == "available"]


def get_reserved_frameworks() -> list[dict]:
    return [f for f in FRAMEWORK_REGISTRY if normalize_text(f.get("status", "")).casefold() != "available"]


def refresh_framework_registry() -> list[dict]:
    refreshed = build_framework_registry()
    FRAMEWORK_REGISTRY[:] = refreshed
    return FRAMEWORK_REGISTRY


def initialize_framework_registry() -> list[dict]:
    return refresh_framework_registry()
