"""Conversation memory recall skill, backed by the on-device SQLite transcript."""
from __future__ import annotations

from memory import MEMORY_INTENT


def handle(text: str, context: dict) -> str | None:
    if not MEMORY_INTENT.search(text):
        return None
    store = context.get("memory")
    if store is None:
        return "I don't have a conversation database available yet."
    excerpts = store.relevant_context(text)
    if not excerpts:
        return "I couldn't find a matching detail in your saved conversations."
    return "I found this in your saved conversations: " + excerpts.replace("\n", ". ")


def register(manager) -> None:
    manager.register("memory", "Recall searchable details from saved conversations.", handle,
                     ("What did I tell you about Iceland?", "Recall our last conversation."))
