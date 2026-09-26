"""Local appearance presets for the desktop and HUD."""
from __future__ import annotations

THEMES: dict[str, dict[str, str]] = {
    "Arc Reactor": {
        "background": "#0b1018", "panel": "#111a26", "panel_alt": "#172333",
        "border": "#26364a", "text": "#e8eef7", "muted": "#8fa1b7",
        "accent": "#69d9ff", "secondary": "#278cff", "success": "#56d6a2",
        "user_bubble": "#172b40", "bot_bubble": "#131f2c",
    },
    "Stark Blue": {
        "background": "#081326", "panel": "#0e1e36", "panel_alt": "#152b49",
        "border": "#284469", "text": "#ecf5ff", "muted": "#91acd0",
        "accent": "#56b8ff", "secondary": "#4774ff", "success": "#50e0c1",
        "user_bubble": "#173455", "bot_bubble": "#112742",
    },
    "Emerald": {
        "background": "#09140f", "panel": "#102219", "panel_alt": "#193326",
        "border": "#2b5540", "text": "#e6fff1", "muted": "#91b5a0",
        "accent": "#59edb3", "secondary": "#24b982", "success": "#8cf0a9",
        "user_bubble": "#183b2b", "bot_bubble": "#14291f",
    },
    "Amber": {
        "background": "#171108", "panel": "#271c0d", "panel_alt": "#392810",
        "border": "#624519", "text": "#fff7e7", "muted": "#c0a87d",
        "accent": "#ffc96b", "secondary": "#e89735", "success": "#a4e5a0",
        "user_bubble": "#453015", "bot_bubble": "#302411",
    },
    "Violet": {
        "background": "#110d1b", "panel": "#1c1530", "panel_alt": "#2b2046",
        "border": "#49346f", "text": "#f5efff", "muted": "#b2a0ce",
        "accent": "#c392ff", "secondary": "#8061ef", "success": "#68e3d0",
        "user_bubble": "#352650", "bot_bubble": "#231b39",
    },
    "Crimson": {
        "background": "#160b10", "panel": "#251117", "panel_alt": "#391922",
        "border": "#612638", "text": "#fff0f4", "muted": "#c59aa6",
        "accent": "#ff7e9f", "secondary": "#e44f74", "success": "#71e2b0",
        "user_bubble": "#48202c", "bot_bubble": "#301820",
    },
}
DEFAULT_THEME = "Arc Reactor"


def get_theme(name: str | None) -> dict[str, str]:
    return THEMES.get(name or DEFAULT_THEME, THEMES[DEFAULT_THEME]).copy()
