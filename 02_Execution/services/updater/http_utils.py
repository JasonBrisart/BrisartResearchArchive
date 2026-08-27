"""
services/updater/http_utils.py

Shared HTTP helpers: URL/host allowlisting (HTTPS-only, no credentials),
request construction, and bounded response reads.
"""

from __future__ import annotations

import urllib.parse
import urllib.request
from typing import Any

from services.updater.constants import ALLOWED_REMOTE_HOSTS, USER_AGENT


def validate_remote_url(url: str, *, allowed_hosts: set[str] | None = None) -> str:
    value = str(url).strip()
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme.casefold() != "https":
        raise ValueError("Update URLs must use HTTPS.")
    hostname = (parsed.hostname or "").casefold()
    hosts = ALLOWED_REMOTE_HOSTS if allowed_hosts is None else {str(h).casefold() for h in allowed_hosts}
    if hostname not in hosts:
        raise ValueError(f"Update URL host is not allowed: {hostname or '<missing>'}")
    if parsed.username or parsed.password:
        raise ValueError("Update URLs cannot contain credentials.")
    return value


def response_final_url(response: Any) -> str:
    getter = getattr(response, "geturl", None)
    if not callable(getter):
        raise ValueError("The update response did not expose a final URL.")
    return validate_remote_url(getter())


def build_request(url: str, accept: str) -> urllib.request.Request:
    validated_url = validate_remote_url(url)
    return urllib.request.Request(
        validated_url,
        headers={"User-Agent": USER_AGENT, "Accept": str(accept), "Cache-Control": "no-cache"},
        method="GET",
    )


def read_bounded_response(response: Any, maximum_bytes: int) -> bytes:
    if maximum_bytes < 1:
        raise ValueError("maximum_bytes must be positive.")
    declared_length = (response.headers.get("Content-Length", "") or "").strip()
    if declared_length:
        try:
            declared_bytes = int(declared_length)
        except ValueError:
            declared_bytes = -1
        if declared_bytes > maximum_bytes:
            raise ValueError(f"Remote response exceeds the allowed size of {maximum_bytes:,} bytes.")
    data = response.read(maximum_bytes + 1)
    if len(data) > maximum_bytes:
        raise ValueError(f"Remote response exceeded the allowed size of {maximum_bytes:,} bytes.")
    return data
