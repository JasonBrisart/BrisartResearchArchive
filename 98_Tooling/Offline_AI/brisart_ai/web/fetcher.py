r"""
File: brisart_ai/web/fetcher.py

Purpose
-------
Retrieve public web responses with size, timeout and redirect controls.

Communication / relationships
-----------------------------
Called by web/crawler.py; uses io/extractor.py and web/policy.py.

Settings / parameters
---------------------
MAX_PAGE_BYTES and REQUEST_TIMEOUT bound fetch operations.

Edge cases
----------
Rejects private initial and redirected URLs, invalid content and oversized
responses.

Known limitations
-----------------
DNS rebinding cannot be fully prevented without address pinning; robots
checks occur in crawler.

Examples
--------
fetch_url("https://example.org/")
"""

from __future__ import annotations

import urllib.error
import urllib.request

from brisart_ai.io.extractor import html_to_text
from brisart_ai.util import normalize_url
from brisart_ai.web.models import FetchResult
from brisart_ai.web.policy import USER_AGENT, is_local_or_private_host
from brisart_url import brisart_urlsplit

class _PublicOnlyRedirect(urllib.request.HTTPRedirectHandler):
    """Reject redirected targets outside the public HTTP(S) web."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = brisart_urlsplit(newurl)
        if target.scheme.casefold() not in ("http", "https") or is_local_or_private_host(target.hostname or ""):
            raise ValueError("redirect to a local, private or unsupported destination")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


MAX_PAGE_BYTES = 2_000_000
REQUEST_TIMEOUT = 15


def fetch_url(url: str) -> FetchResult:
    normalized = normalize_url(url)
    if not normalized:
        return FetchResult(
            url=str(url), status=0, content_type="", title="", text="",
            links=[], error="invalid URL",
        )

    target = brisart_urlsplit(normalized)
    if target.scheme.casefold() not in ("http", "https") or is_local_or_private_host(target.hostname or ""):
        return FetchResult(url=normalized, status=0, content_type="", title="",
                           text="", links=[], error="private or unsupported destination")
    request = urllib.request.Request(
        normalized,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.1",
        },
    )

    try:
        with urllib.request.build_opener(_PublicOnlyRedirect()).open(request, timeout=REQUEST_TIMEOUT) as response:
            final_url = response.geturl() if hasattr(response, "geturl") else normalized
            final_target = brisart_urlsplit(final_url)
            if final_target.scheme.casefold() not in ("http", "https") or is_local_or_private_host(final_target.hostname or ""):
                raise ValueError("response resolved to a private or unsupported destination")
            status = int(getattr(response, "status", 200))
            content_type = response.headers.get("Content-Type", "")
            raw = response.read(MAX_PAGE_BYTES + 1)
            if len(raw) > MAX_PAGE_BYTES:
                return FetchResult(
                    url=final_url, status=status, content_type=content_type,
                    title="", text="", links=[], error="page too large",
                )
            charset = response.headers.get_content_charset() or "utf-8"
            decoded = raw.decode(charset, errors="replace")
            lowered_type = content_type.casefold()
            if "text/plain" in lowered_type:
                return FetchResult(
                    url=final_url, status=status, content_type=content_type,
                    title=final_url, text=decoded.strip(), links=[],
                )
            if "text/html" not in lowered_type and "application/xhtml" not in lowered_type:
                return FetchResult(
                    url=final_url, status=status, content_type=content_type,
                    title="", text="", links=[], error="unsupported content type",
                )
            title, text, links = html_to_text(decoded, base_url=final_url)
            return FetchResult(
                url=final_url, status=status, content_type=content_type,
                title=title or final_url, text=text, links=links,
            )
    except urllib.error.HTTPError as exc:
        return FetchResult(
            url=normalized, status=int(exc.code), content_type="",
            title="", text="", links=[], error=f"HTTP {exc.code}",
        )
    except urllib.error.URLError as exc:
        return FetchResult(
            url=normalized, status=0, content_type="", title="", text="",
            links=[], error=f"network error: {exc.reason}",
        )
    except Exception as exc:
        return FetchResult(
            url=normalized, status=0, content_type="", title="", text="",
            links=[], error=str(exc),
        )
