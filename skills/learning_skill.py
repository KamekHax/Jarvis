"""User-directed, local-only knowledge capture and recall."""
from __future__ import annotations

import re
from pathlib import Path

LEARN = re.compile(r"^(?:learn that|learn this|remember that|teach yourself that|save this fact)\s*[:,-]?\s*(.+)$", re.I | re.S)


def handle(text: str, context: dict) -> str | None:
    manager = context.get("skills")
    manager_setting = bool(manager and "learning" in manager.enabled)
    if not manager_setting:
        return None
    match = LEARN.match(text.strip())
    if match:
        store = context.get("memory")
        if store is None:
            return "I can't save a learning note because local memory isn't available."
        note = match.group(1).strip()
        store.save_knowledge(note[:120], note, "voice note")
        return "I saved that note to local JARVIS memory. This is searchable retrieval memory, not neural-model training."

    normalized = text.lower().strip()
    if normalized in {"what have you learned", "list what you learned", "show learned notes", "what have you learned from me"}:
        store = context.get("memory")
        notes = store.learned_knowledge(limit=10) if store else []
        if not notes:
            return "I don't have any taught notes yet. Say ‘learn that …’ to teach me a fact."
        return "Here are your recent local notes: " + "; ".join(f"{item['title']}: {item['content'][:180]}" for item in notes)

    if normalized in {"learn from a file", "learn from file", "teach yourself from a file", "learn a local file"}:
        if not context.get("permissions", {}).get("allow_local_file_learning", False):
            return "Reading local files is disabled. Enable ‘Learn from selected local files’ in Security & permissions, then ask me again."
        action = context.get("actions", {}).get("choose_file_to_learn")
        if not action:
            return "Open JARVIS on the desktop to select a local file to learn from."
        action()
        return "Opening the local file picker. I'll only read the file you explicitly select."
    return None


def register(manager) -> None:
    manager.register("learning", "Save voice-taught notes and search explicitly selected local files, entirely on-device.", handle,
                     ("Learn that my project uses Python 3.11", "What have you learned?", "Learn from a file"))
