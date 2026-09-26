"""Safe discovery of built-in and user-supplied local JSON color themes."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app_paths import user_data_root
from themes import DEFAULT_THEME, THEMES

COLOR_KEYS = {"background", "panel", "panel_alt", "border", "text", "muted", "accent", "secondary", "success", "user_bubble", "bot_bubble"}
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_THEMES = 100


def load_themes(directory: Path | None = None) -> dict[str, dict[str, str]]:
    choices = {name: dict(colors) for name, colors in THEMES.items()}
    directory = directory or user_data_root() / "data" / "themes"
    try:
        files = sorted(directory.glob("*.json"))[:MAX_THEMES]
    except OSError:
        return choices
    for file in files:
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
            name = str(data.get("name", file.stem)).strip()[:48]
            colors = data.get("colors", data)
            if not name or not isinstance(colors, dict):
                continue
            if not COLOR_KEYS.issubset(colors):
                continue
            clean = {key: str(colors[key]) for key in COLOR_KEYS}
            if not all(COLOR.fullmatch(value) for value in clean.values()):
                continue
            choices[name] = clean
        except (OSError, json.JSONDecodeError, TypeError, AttributeError):
            continue
    return choices


def validate_theme(theme: dict[str, Any]) -> dict[str, Any]:
    colors = theme.get("colors", theme)
    if not isinstance(colors, dict) or not COLOR_KEYS.issubset(colors):
        raise ValueError("A theme needs all 11 named color fields.")
    clean = {key: str(colors[key]) for key in COLOR_KEYS}
    if not all(COLOR.fullmatch(value) for value in clean.values()):
        raise ValueError("Theme colors must use #RRGGBB hex notation.")
    return clean


def save_theme(name: str, colors: dict[str, Any], directory: Path | None = None) -> Path:
    name = " ".join(name.split())[:48]
    if not name or name in THEMES:
        raise ValueError("Choose a unique, non-empty theme name.")
    clean = validate_theme(colors)
    directory = directory or user_data_root() / "data" / "themes"
    directory.mkdir(parents=True, exist_ok=True)
    filename = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.lower()).strip("-") or "custom-theme"
    target = directory / f"{filename}.json"
    if target.exists():
        raise FileExistsError(f"A custom theme file already exists: {target.name}")
    target.write_text(json.dumps({"name": name, "colors": clean}, indent=2) + "\n", encoding="utf-8")
    return target
