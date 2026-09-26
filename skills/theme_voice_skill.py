"""Voice commands for selecting locally installed themes and voices."""
from __future__ import annotations
import re


def handle(text: str, context: dict) -> str | None:
    actions = context.get("actions", {})
    theme = re.match(r"^(?:switch|change|set) theme (?:to )?(.+?)[.!?]*$", text.strip(), re.I)
    if theme:
        callback = actions.get("set_theme")
        if not callback:
            return "Theme switching is available in JARVIS Settings."
        return callback(theme.group(1).strip())
    voice = re.match(r"^(?:switch|change|set) voice (?:to )?(.+?)[.!?]*$", text.strip(), re.I)
    if voice:
        callback = actions.get("set_voice")
        if not callback:
            return "Voice switching is available in JARVIS Settings."
        return callback(voice.group(1).strip())
    return None


def register(manager) -> None:
    manager.register("theme_voice", "Switch between locally installed appearance themes and system speech voices by voice command.", handle,
                     ("Switch theme to Emerald", "Change voice to Calm"))
