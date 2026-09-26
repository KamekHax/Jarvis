"""Explicit, bounded web lookup. Search URLs are opened by the OS default browser."""
from __future__ import annotations

import base64
import html
from html.parser import HTMLParser
import re
from urllib.error import URLError
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen
import webbrowser
from typing import Any


SEARCH_URLS = {
    "Google": "https://www.google.com/search?q={query}",
    "Bing": "https://www.bing.com/search?q={query}",
    "DuckDuckGo": "https://duckduckgo.com/?q={query}",
}
RESULTS_URL = "https://www.bing.com/search?q={query}&setlang=en-US&cc=US&mkt=en-US"
USER_AGENT = "Mozilla/5.0 (compatible; JARVIS-Local/1.0; +https://github.com/KamekHax/Jarvis)"
MAX_RESPONSE_BYTES = 1_000_000


class _BingResults(HTMLParser):
    """Parse only organic-result titles, destinations and snippets; ignore all scripts."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[dict[str, str]] = []
        self.current: dict[str, Any] | None = None
        self.result_depth = 0
        self.title_depth = 0
        self.snippet_depth = 0
        self.title_parts: list[str] = []
        self.snippet_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        classes = (attr.get("class") or "").split()
        if tag == "li" and "b_algo" in classes:
            self.current = {"href": ""}
            self.result_depth = 1
            self.title_depth = 0
            self.snippet_depth = 0
            self.title_parts, self.snippet_parts = [], []
            return
        if self.current is None:
            return
        if tag == "li":
            self.result_depth += 1
        if tag == "h2":
            self.title_depth += 1
        if self.title_depth and tag == "a" and not self.current.get("href"):
            self.current["href"] = attr.get("href") or ""
        if "b_caption" in classes or "b_lineclamp" in classes:
            if not self.snippet_depth:
                self.snippet_depth = 1
            else:
                self.snippet_depth += 1
        elif self.snippet_depth:
            self.snippet_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self.current is None:
            return
        if self.title_depth and tag == "h2":
            self.title_depth -= 1
        if self.snippet_depth:
            self.snippet_depth -= 1
        if tag == "li":
            self.result_depth -= 1
            if self.result_depth <= 0:
                title = clean_text(" ".join(self.title_parts))
                snippet = clean_text(" ".join(self.snippet_parts))
                target = decode_bing_url(str(self.current.get("href", "")))
                if title and target:
                    self.items.append({"title": title[:220], "url": target, "snippet": snippet[:700]})
                self.current = None

    def handle_data(self, data: str) -> None:
        if self.current is None:
            return
        if self.title_depth:
            self.title_parts.append(data)
        elif self.snippet_depth:
            self.snippet_parts.append(data)


def clean_text(value: str) -> str:
    value = html.unescape(re.sub(r"<[^>]*>", " ", value))
    return re.sub(r"\s+", " ", value).strip()


def decode_bing_url(raw_url: str) -> str:
    raw_url = html.unescape(raw_url.strip())
    parsed = urlparse(raw_url)
    target = raw_url
    if parsed.hostname and parsed.hostname.lower().endswith("bing.com"):
        encoded = parse_qs(parsed.query).get("u", [""])[0]
        if encoded.startswith("a1"):
            try:
                target = base64.urlsafe_b64decode(encoded[2:] + "==").decode("utf-8", "strict")
            except (ValueError, UnicodeError):
                return ""
    target = unquote(target).strip()
    final = urlparse(target)
    if final.scheme not in {"https", "http"} or not final.hostname or final.hostname.endswith("bing.com"):
        return ""
    return target


def search_results(query: str, limit: int = 5, timeout: float = 12.0) -> list[dict[str, str]]:
    """Fetch a bounded set of public result summaries; never fetch result destination URLs."""
    query = " ".join(query.split())
    if not query:
        raise ValueError("Give JARVIS a topic to search for.")
    if len(query) > 240:
        raise ValueError("Online search queries are limited to 240 characters.")
    url = RESULTS_URL.format(query=quote_plus(query))
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
    try:
        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get_content_type().lower()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                raise RuntimeError("The search provider returned an unexpected response format.")
            source = response.read(MAX_RESPONSE_BYTES + 1)
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"The web search request failed: {exc}") from exc
    if len(source) > MAX_RESPONSE_BYTES:
        source = source[:MAX_RESPONSE_BYTES]
    text = source.decode("utf-8", "replace")
    if "anomaly-modal" in text or "captcha" in text.lower():
        raise RuntimeError("The search provider asked for a verification step; I opened the browser results instead.")
    parser = _BingResults()
    parser.feed(text)
    # Deduplicate, keep only regular web links, and do not fetch the result pages.
    results, seen = [], set()
    for item in parser.items:
        if item["url"] not in seen:
            seen.add(item["url"])
            results.append(item)
        if len(results) >= max(1, min(limit, 8)):
            break
    return results


def search_browser_url(query: str, engine: str = "Google") -> str:
    selected = engine if engine in SEARCH_URLS else "Google"
    return SEARCH_URLS[selected].format(query=quote_plus(" ".join(query.split())[:240]))


def open_search_in_default_browser(query: str, engine: str = "Google") -> bool:
    """Hand a search URL to Python's platform-default browser integration."""
    try:
        return bool(webbrowser.open(search_browser_url(query, engine), new=2, autoraise=True))
    except Exception:
        return False
