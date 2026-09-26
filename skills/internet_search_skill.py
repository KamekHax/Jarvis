"""Explicit user-triggered web research; does not inspect local conversations/files."""
from __future__ import annotations

import re


SEARCH_PATTERNS = (
    re.compile(r"^(?:google|bing|duckduckgo)\s+(?:for\s+)?(.+)$", re.I),
    re.compile(r"^(?:search|look\s+up|find)\s+(?:(?:the\s+)?(?:web|internet|online)\s+)?(?:for\s+)?(.+?)(?:\s+online)?$", re.I),
    re.compile(r"^(?:research|look\s+online\s+for)\s+(.+)$", re.I),
)


def match(text: str) -> bool:
    return any(pattern.match(text.strip()) for pattern in SEARCH_PATTERNS)


def extract_query(text: str) -> str:
    raw = text.strip()
    for pattern in SEARCH_PATTERNS:
        found = pattern.match(raw)
        if found:
            query = found.group(1).strip().strip(" .?!,;")
            return query[:240]
    return ""


def handle(text: str, context: dict) -> str | None:
    query = extract_query(text)
    if not query:
        return "Tell me what to search for, for example: ‘Google today’s weather in Oslo.’"
    settings = context.get("permissions", {})
    if not settings.get("allow_internet_search", False):
        return "Online search is off. Enable ‘Allow explicitly requested web searches’ in Settings → Security & permissions, then ask again. I did not send this query anywhere."
    action = context.get("actions", {}).get("search_web")
    if not callable(action):
        return "The local web-search action is unavailable. Open Settings and check the network-search setup."
    try:
        return action(query)
    except Exception as exc:
        return f"I could not complete that web search: {exc}"


def register(manager) -> None:
    manager.register(
        "internet_search", "Search the web only when explicitly asked; show cited snippets and open results in your default browser.",
        handle, ("Google the current weather in Oslo", "Search the web for official Python tkinter documentation"),
        permissions=("allow_internet_search",), matcher=match,
    )
