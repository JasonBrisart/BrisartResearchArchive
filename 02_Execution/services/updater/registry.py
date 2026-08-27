"""
services/updater/registry.py
Fetches this app's entry from the combined Brisart Tooling registry
page (one JSON object embedded between marker comments, one entry per
app). Defines the two exception types used throughout the update
system, and the RegistryEntry data shape.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from services.updater.constants import (
    APP_REGISTRY_ID,
    MAX_REGISTRY_RESPONSE_BYTES,
    REGISTRY_END_MARKER,
    REGISTRY_PAGE_URL,
    REGISTRY_START_MARKER,
    VERSION_TIMEOUT_SECONDS,
)
from services.updater.http_utils import build_request, read_bounded_response, response_final_url


class RegistryError(Exception):
    """Could not reach, parse, or find this app's entry in the registry page."""


class VerificationError(Exception):
    """The downloaded release's hash or signature did not check out. This
    is the hard gate: nothing in install.py or exe_swap.py is ever
    reached unless verification passes."""


@dataclass(slots=True)
class RegistryEntry:
    version: str
    download_url: str
    sha256: str
    signature: str
    asset_kind: str = "zip"  # "zip" (source-mode overwrite) or "exe" (frozen swap)
    # Optional short, human-readable summary of what changed in this
    # release. Entirely optional in the registry JSON -- if the field is
    # missing, this stays "" and the GUI falls back to a generic message
    # instead of showing an empty/blank changelog section.
    changelog: str = ""


def fetch_registry_entry(app_id: str = APP_REGISTRY_ID) -> RegistryEntry:
    request = build_request(REGISTRY_PAGE_URL, "text/html")
    try:
        with urllib.request.urlopen(request, timeout=VERSION_TIMEOUT_SECONDS) as response:
            response_final_url(response)
            raw = read_bounded_response(response, MAX_REGISTRY_RESPONSE_BYTES)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        raise RegistryError(f"Could not reach {REGISTRY_PAGE_URL}: {exc}") from exc

    html = raw.decode("utf-8", errors="replace")
    match = re.search(
        re.escape(REGISTRY_START_MARKER) + r"(.*?)" + re.escape(REGISTRY_END_MARKER),
        html,
        re.DOTALL,
    )
    if not match:
        raise RegistryError(
            f"Could not find registry markers on {REGISTRY_PAGE_URL}. "
            f"Confirm the Custom HTML block was published with markers intact."
        )

    json_text = match.group(1).strip()
    json_text = json_text.replace("&quot;", '"').replace("&#34;", '"').replace("&amp;", "&")
    try:
        registry = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise RegistryError(f"Registry JSON was not valid JSON: {exc}") from exc

    entry = registry.get(app_id)
    if entry is None:
        raise RegistryError(f"No entry named {app_id!r} found in the registry page.")

    required = ("version", "download_url", "sha256", "signature")
    missing = [f for f in required if f not in entry]
    if missing:
        raise RegistryError(f"Registry entry {app_id!r} is missing fields: {missing}")

    return RegistryEntry(
        version=entry["version"],
        download_url=entry["download_url"],
        sha256=entry["sha256"],
        signature=entry["signature"],
        asset_kind=str(entry.get("asset_kind", "zip")).strip().lower() or "zip",
        changelog=str(entry.get("changelog", "") or "").strip(),
    )
