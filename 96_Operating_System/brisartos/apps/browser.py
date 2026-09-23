"""
BrisartOS Built-In Browser Module

Pure Python.
No dependencies.
No tracking.
Standard library only.

This is the OS-integrated browser layer.
"""

from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.request import Request, urlopen


APP_NAME = "BrisartOS Browser"
VERSION = "0.1.0-alpha"
USER_AGENT = "BrisartOS-Browser/0.1.0-alpha"
MAX_PAGE_BYTES = 1_000_000


class TextHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        if tag in {"script", "style", "noscript"}:
            self.skip_depth += 1
            return

        if tag in {"p", "div", "br", "h1", "h2", "h3", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag in {"script", "style", "noscript"} and self.skip_depth:
            self.skip_depth -= 1
            return

        if tag in {"p", "div", "h1", "h2", "h3", "li"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip_depth:
            return

        cleaned = " ".join(data.split())

        if cleaned:
            self.parts.append(cleaned)

    def text(self):
        raw = " ".join(self.parts)
        lines = [line.strip() for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)


def normalize_url(value):
    value = value.strip()

    if not value:
        raise ValueError("URL is required")

    parsed = urlparse(value)

    if not parsed.scheme:
        return "https://" + value

    return value


def fetch_page(url):
    url = normalize_url(url)

    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT
        }
    )

    with urlopen(request, timeout=15) as response:
        raw = response.read(MAX_PAGE_BYTES + 1)

        if len(raw) > MAX_PAGE_BYTES:
            raise ValueError("Page exceeds BrisartOS browser size limit")

        charset = response.headers.get_content_charset() or "utf-8"
        final_url = response.geturl()

    source = raw.decode(charset, errors="replace")

    parser = TextHTMLParser()
    parser.feed(source)

    return {
        "url": final_url,
        "source": source,
        "text": parser.text(),
    }


def open_url(url):
    page = fetch_page(url)

    print()
    print("=" * 72)
    print(APP_NAME)
    print("=" * 72)
    print("URL:", page["url"])
    print("=" * 72)
    print()

    if page["text"]:
        print(page["text"])
    else:
        print("[No readable text found]")

    print()
    print("=" * 72)
    print("End of page")
    print("=" * 72)
    print()


def main(args=None):
    if args is None:
        args = []

    if not args:
        print("usage: browser <url>")
        return 1

    open_url(args[0])
    return 0