"""Local music playback skill; reads only audio files in the chosen music folder."""
from __future__ import annotations

import re

PATTERNS = {
    "next": re.compile(r"^(?:next(?:\s+song|\s+track)?|skip(?:\s+song|\s+track)?|next\s+track)$", re.I),
    "pause": re.compile(r"^(?:pause(?:\s+the)?\s+music|pause\s+playback)$", re.I),
    "resume": re.compile(r"^(?:resume(?:\s+the)?\s+music|continue\s+the\s+music|unpause)$", re.I),
    "stop": re.compile(r"^(?:stop(?:\s+the)?\s+music|stop\s+playback)$", re.I),
    "play": re.compile(r"^(?:play(?:\s+music)?|play\s+song\s+(.+)|play\s+(.+?))(?:\s+locally)?$", re.I),
}


def match(text: str) -> bool:
    return any(pattern.match(text.strip()) for pattern in PATTERNS.values())


def handle(text: str, context: dict) -> str | None:
    if not context.get("permissions", {}).get("allow_local_music", False):
        return "Local music playback is disabled. Enable ‘Allow local music playback’ in Settings and choose your music folder first."
    player = context.get("actions", {}).get("music_player")
    if player is None:
        return "The local music player isn't ready. Check the audio playback setup in Settings."
    for command, pattern in PATTERNS.items():
        found = pattern.match(text.strip())
        if not found:
            continue
        if command == "play":
            query = next((value for value in found.groups() if value), "")
            return player.play(query)
        if command == "next":
            return player.next()
        if command == "pause":
            return player.pause()
        if command == "resume":
            return player.resume()
        if command == "stop":
            return player.stop()
    return None


def register(manager) -> None:
    manager.register("music", "Play, pause, resume and skip audio from a local music folder.",
                     handle, ("Play music", "Play song Moonlight", "Next track", "Pause the music"),
                     permissions=("allow_local_music",), matcher=match)
