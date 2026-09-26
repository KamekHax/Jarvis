"""Locations for bundled assets and writable per-user JARVIS state."""
from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

APP_NAME = "JARVIS-Local"


def bundle_root() -> Path:
    """Read-only asset directory inside a PyInstaller bundle or this source checkout."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


def user_data_root() -> Path:
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parent
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / APP_NAME
