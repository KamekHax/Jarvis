"""Skill listing and discoverability commands."""
from __future__ import annotations


def handle(text: str, context: dict) -> str | None:
    if text.lower().strip() not in {"skills", "list skills", "what skills do you have", "what can you do"}:
        return None
    manager = context.get("skills")
    if manager is None:
        return "I don't have a skill manager available."
    enabled = [skill for skill in manager.list_skills() if skill["enabled"]]
    if not enabled:
        return "No skills are enabled. Open Skills in the desktop app to turn them on."
    result = ["Here's what I can do with the skills you enabled:"]
    for skill in enabled:
        result.append(f"• {skill['name']}: {skill['description']}")
        if skill["examples"]:
            result.append("  Try: " + "; ".join(skill["examples"]))
    return "\n".join(result)


def register(manager) -> None:
    manager.register("skills_help", "List the enabled skills and example voice prompts.", handle,
                     ("List skills", "What skills do you have?"))
