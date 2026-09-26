"""Persisted desktop preferences, startup registration, and hotkey definitions."""
from __future__ import annotations

import json
import copy
import os
import platform
import plistlib
import shlex
import sys
from pathlib import Path
from typing import Any
from app_paths import user_data_root
from themes import DEFAULT_THEME

ROOT = Path(__file__).resolve().parent
DEFAULT_SETTINGS: dict[str, Any] = {
    "scale": 1.0,
    "opacity": 0.93,
    "animation_performance": "medium",
    "always_on_top": True,
    "click_through": False,
    "launch_on_startup": False,
    "hotkey_overlay": "ctrl+alt+o",
    "hotkey_command": "ctrl+alt+k",
    "hotkey_everyday": "ctrl+alt+j",
    "hotkey_voice": "ctrl+alt+v",
    "theme": DEFAULT_THEME,
    "voice_id": "",
    "voice_style": "Balanced",
    "workspace_dir": "",
    "approved_apps": {},
    "allow_app_launching": False,
    "allow_workspace_writes": False,
    "allow_local_file_learning": False,
    "allow_user_plugins": False,
    "allow_external_integrations": False,
    "mode": "everyday",
    "overlay_geometry": "380x380+40+40",
}


def load_settings(path: Path | None = None) -> dict[str, Any]:
    path = path or user_data_root() / "data" / "desktop_settings.json"
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    if path.exists():
        try:
            supplied = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(supplied, dict):
                settings.update(supplied)
        except (OSError, json.JSONDecodeError):
            pass
    try:
        settings["scale"] = max(0.65, min(1.5, float(settings.get("scale", 1.0))))
    except (TypeError, ValueError):
        settings["scale"] = DEFAULT_SETTINGS["scale"]
    try:
        settings["opacity"] = max(0.45, min(1.0, float(settings.get("opacity", 0.93))))
    except (TypeError, ValueError):
        settings["opacity"] = DEFAULT_SETTINGS["opacity"]
    if settings.get("animation_performance") not in {"low", "medium", "high"}:
        settings["animation_performance"] = "medium"
    if settings.get("mode") not in {"everyday", "overlay", "command_center"}:
        settings["mode"] = "everyday"
    if not isinstance(settings.get("approved_apps"), dict):
        settings["approved_apps"] = {}
    else:
        settings["approved_apps"] = {
            " ".join(str(name).strip().lower().split()): str(path)
            for name, path in settings["approved_apps"].items()
            if str(name).strip() and str(path).strip()
        }
    for key in ("allow_app_launching", "allow_workspace_writes", "allow_local_file_learning",
                "allow_user_plugins", "allow_external_integrations"):
        settings[key] = settings.get(key, False) if isinstance(settings.get(key, False), bool) else False
    return settings


def save_settings(settings: dict[str, Any], path: Path | None = None) -> None:
    path = path or user_data_root() / "data" / "desktop_settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _startup_target() -> tuple[str, Path]:
    system = platform.system()
    if system == "Windows":
        return system, Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "Microsoft/Windows/Start Menu/Programs/Startup/JARVIS-Local.cmd"
    if system == "Darwin":
        return system, Path.home() / "Library/LaunchAgents/im.manus.jarvis-local.plist"
    return system, Path.home() / ".config/autostart/jarvis-local.desktop"


def set_startup_enabled(enabled: bool, project: Path = ROOT) -> None:
    """Register or remove this app in the current user's OS login startup folder."""
    system, target = _startup_target()
    if not enabled:
        target.unlink(missing_ok=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        command = [str(executable)]
        if system == "Windows":
            content = f'@start "JARVIS Local" "{executable}"\r\n'
        else:
            content = None
    else:
        python = Path(sys.executable).resolve()
        entry = Path(project) / "run.py"
        command = [str(python), str(entry)]
        if system == "Windows":
            content = f'@start "JARVIS Local" "{python}" "{entry}"\r\n'
        else:
            content = None
    if system == "Windows":
        target.write_text(content, encoding="utf-8")
    elif system == "Darwin":
        target.write_bytes(plistlib.dumps({
            "Label": "im.manus.jarvis-local",
            "ProgramArguments": command,
            "RunAtLoad": True,
            "KeepAlive": False,
        }))
    else:
        target.write_text(
            "[Desktop Entry]\nType=Application\nName=JARVIS Local\n"
            f"Exec={shlex.join(command)}\nX-GNOME-Autostart-enabled=true\n",
            encoding="utf-8",
        )
