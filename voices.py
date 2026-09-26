"""Offline TTS voice profiles and discovery of installed system voices."""
from __future__ import annotations
from typing import Any

VOICE_STYLES = {
    "Balanced": {"rate": 178, "volume": 0.92},
    "Calm": {"rate": 154, "volume": 0.84},
    "Energetic": {"rate": 198, "volume": 1.0},
    "Concise": {"rate": 188, "volume": 0.96},
}


def discover_voices(engine: Any) -> list[dict[str, str]]:
    """Return display names and opaque IDs for locally installed pyttsx3 voices."""
    try:
        return [
            {"name": str(getattr(voice, "name", "Local voice")), "id": str(voice.id)}
            for voice in engine.getProperty("voices")
        ]
    except Exception:
        return []


def find_voice_id(voices: list[dict[str, str]], display_name: str) -> str:
    if display_name == "System default":
        return ""
    for voice in voices:
        if voice["name"] == display_name:
            return voice["id"]
    return ""
