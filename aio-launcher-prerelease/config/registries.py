"""
File: config/registries.py

Purpose:
Discover framework modules, normalize framework metadata, maintain the
framework registry, and resolve application page renderers.

Communication / relationships:
- Reads framework.py modules under frameworks/.
- Provides registry lookups to services/framework_service.py.
- Provides page navigation metadata to gui/components/sidebar.py.
- Lazily imports page renderers from gui/pages/.

Settings / parameters:
- RESERVED_FRAMEWORKS defines framework placeholders.
- FRAMEWORK_DISPLAY_ORDER controls framework display order.
- NAV_ITEMS controls the primary sidebar navigation.
- SETTINGS_NAV_ITEM defines the bottom-pinned Settings entry.
- DEFAULT_PAGE determines the page shown at application startup.

Edge cases:
- Missing or malformed framework modules are isolated and recorded.
- Duplicate framework IDs are rejected without stopping discovery.
- Missing metadata fields are normalized to safe defaults.
- Page imports remain lazy so headless tests do not import Tkinter pages.

Known limitations:
- Reserved frameworks are informational placeholders and cannot run.
- Page renderer caching requires a process restart to detect page-module
  changes made while the application is running.

Examples:
- get_framework("TFL")
- get_available_frameworks()
- get_page_renderer("Dashboard")
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

EXECUTION_DIR = Path(__file__).resolve().parents[1]
FRAMEWORKS_DIR = EXECUTION_DIR / "frameworks"

RESERVED_FRAMEWORKS = [
    {
        "id": "SST",
        "name": "Simulation Synchronization Theory",
        "status": "Coming Soon",
        "module": "",
        "runner_module": "",
        "runner_class": "",
        "description": "Reserved framework slot.",
        "features": [],
    },
    {
        "id": "IRE",
        "name": "Intent Resolution Engine",
        "status": "Coming Soon",
        "module": "",
        "runner_module": "",
        "runner_class": "",
        "description": "Reserved framework slot.",
        "features": [],
    },
    {
        "id": "PFT",
        "name": "Perceptual Framing Theory",
        "status": "Coming Soon",
        "module": "",
        "runner_module": "",
        "runner_class": "",
        "description": "Reserved framework slot.",
        "features": [],
    },
    {
        "id": "PCT",
        "name": "Predictive Convergence Theory",
        "status": "Coming Soon",
        "module": "",
        "runner_module": "",
        "runner_class": "",
        "description": "Reserved framework slot.",
        "features": [],
    },
    {
        "id": "RIET",
        "name": "Residual Identity Echo Theory",
        "status": "Coming Soon",
        "module": "",
        "runner_module": "",
        "runner_class": "",
        "description": "Reserved framework slot.",
        "features": [],
    },
]

FRAMEWORK_DISPLAY_ORDER = ["TFL", "SST", "IRE", "PFT", "PCT", "RIET"]

REQUIRED_METADATA_KEYS = [
    "id",
    "name",
    "status",
    "module",
    "runner_module",
    "runner_class",
    "description",
    "features",
]

PAGE_ALIASES = {
    "Home": "Dashboard",
    "Execution": "Frameworks",
    "Analysis": "Results",
    "Documentation": "Archive",
    "System": "Settings",
}

NAV_ITEMS = [
    ("Dashboard", "\u2302"),
    ("Frameworks", "\U0001F9EA"),
    ("Results", "\U0001F4CA"),
    ("Archive", "\U0001F4DA"),
]

SETTINGS_NAV_ITEM = ("Settings", "\u2699")
DEFAULT_PAGE = "Dashboard"


# ============================================================
# Shared mutable state
# ============================================================

DISCOVERY_ERRORS: list[dict[str, str]] = []
FRAMEWORK_REGISTRY: list[dict] = []
_PAGE_REGISTRY_CACHE: dict | None = None


# ============================================================
# Page registry
# ============================================================

def normalize_page_name(name: str) -> str:
    return PAGE_ALIASES.get(name, name)


def get_page_registry() -> dict:
    global _PAGE_REGISTRY_CACHE

    if _PAGE_REGISTRY_CACHE is None:
        from gui.pages import (
            archive_page,
            dashboard_page,
            frameworks_page,
            results_page,
            settings_page,
        )

        _PAGE_REGISTRY_CACHE = {
            "Dashboard": dashboard_page.render,
            "Frameworks": frameworks_page.render,
            "Results": results_page.render,
            "Archive": archive_page.render,
            "Settings": settings_page.render,
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
        "traceback": "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        ),
    }
    DISCOVERY_ERRORS.append(error)

    print(
        f"Framework discovery skipped {module_name}: "
        f"{error['error_type']}: {error['message']}"
    )


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

    for key in (
        "id",
        "name",
        "status",
        "module",
        "runner_module",
        "runner_class",
        "description",
    ):
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
# Framework discovery
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

    try:
        paths = list(FRAMEWORKS_DIR.iterdir())
    except OSError as exc:
        record_discovery_error(str(FRAMEWORKS_DIR), exc)
        return []

    module_names = []

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


def extract_framework_metadata(
    module_name: str,
    module: ModuleType,
) -> dict | None:
    metadata = getattr(module, "FRAMEWORK_METADATA", None)

    if metadata is None:
        record_discovery_error(
            module_name,
            AttributeError("FRAMEWORK_METADATA not found"),
        )
        return None

    if not is_valid_metadata(metadata):
        record_discovery_error(
            module_name,
            ValueError("FRAMEWORK_METADATA is invalid"),
        )
        return None

    try:
        normalized = normalize_metadata(metadata)
    except Exception as exc:
        record_discovery_error(module_name, exc)
        return None

    if not normalized["module"]:
        normalized["module"] = module_name

    return normalized


def discover_frameworks() -> list[dict]:
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
            record_discovery_error(
                module_name,
                ValueError(f"Duplicate framework ID: {framework_id}"),
            )
            continue

        discovered_ids.add(framework_id)
        discovered.append(metadata)

    return discovered


# ============================================================
# Registry construction and lookup
# ============================================================

def sort_frameworks(frameworks: list[dict]) -> list[dict]:
    order_lookup = {
        framework_id: index
        for index, framework_id in enumerate(FRAMEWORK_DISPLAY_ORDER)
    }

    def sort_key(framework: dict) -> tuple[int, str]:
        framework_id = normalize_text(framework.get("id", ""))
        return (
            order_lookup.get(framework_id, 999),
            framework_id.casefold(),
        )

    return sorted(frameworks, key=sort_key)


def build_framework_registry() -> list[dict]:
    registry = []
    discovered = discover_frameworks()
    discovered_ids = {framework["id"] for framework in discovered}

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
    return [
        framework
        for framework in FRAMEWORK_REGISTRY
        if normalize_text(framework.get("status", "")).casefold()
        == "available"
    ]


def get_reserved_frameworks() -> list[dict]:
    return [
        framework
        for framework in FRAMEWORK_REGISTRY
        if normalize_text(framework.get("status", "")).casefold()
        != "available"
    ]


def refresh_framework_registry() -> list[dict]:
    refreshed = build_framework_registry()
    FRAMEWORK_REGISTRY[:] = refreshed
    return FRAMEWORK_REGISTRY


def initialize_framework_registry() -> list[dict]:
    return refresh_framework_registry()


__all__ = [
    "EXECUTION_DIR",
    "FRAMEWORKS_DIR",
    "RESERVED_FRAMEWORKS",
    "FRAMEWORK_DISPLAY_ORDER",
    "REQUIRED_METADATA_KEYS",
    "PAGE_ALIASES",
    "NAV_ITEMS",
    "SETTINGS_NAV_ITEM",
    "DEFAULT_PAGE",
    "DISCOVERY_ERRORS",
    "FRAMEWORK_REGISTRY",
    "normalize_page_name",
    "get_page_registry",
    "get_page_renderer",
    "clear_discovery_errors",
    "record_discovery_error",
    "get_discovery_errors",
    "normalize_text",
    "normalize_features",
    "normalize_metadata",
    "is_valid_metadata",
    "is_discoverable_framework_directory",
    "discover_framework_module_names",
    "import_framework_module",
    "extract_framework_metadata",
    "discover_frameworks",
    "sort_frameworks",
    "build_framework_registry",
    "framework_id_matches",
    "get_framework",
    "get_available_frameworks",
    "get_reserved_frameworks",
    "refresh_framework_registry",
    "initialize_framework_registry",
]