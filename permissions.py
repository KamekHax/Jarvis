"""Granular opt-in permissions for local JARVIS capabilities.

Local application launch is restricted to explicit absolute-path allow-lists and never
uses a command shell. This is a policy gate, not an OS sandbox.
"""
from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_PERMISSIONS: dict[str, bool] = {
    "allow_app_launching": False,
    "allow_workspace_writes": False,
    "allow_local_file_learning": False,
    "allow_user_plugins": False,
    "allow_external_integrations": False,
}


def enabled(settings: dict[str, Any], permission: str) -> bool:
    return bool(settings.get(permission, DEFAULT_PERMISSIONS.get(permission, False)))


def launch_approved_app(settings: dict[str, Any], name: str) -> str:
    if not enabled(settings, "allow_app_launching"):
        return "Application launching is blocked. Enable ‘Allow launching approved apps’ in Security & permissions first."
    apps = settings.get("approved_apps", {})
    key = " ".join(name.strip().lower().split())
    if not isinstance(apps, dict) or key not in apps:
        allowed = ", ".join(sorted(apps)) if isinstance(apps, dict) else ""
        return f"‘{name}’ is not on JARVIS’s approved-app list. Add it in Security & permissions. Approved apps: {allowed or 'none'}"
    raw_path = apps[key]
    try:
        target = Path(str(raw_path)).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        return f"The approved application ‘{name}’ could not be found at its saved path. Remove it and add the current app path in Settings."
    if not target.is_file() and not (platform.system() == "Darwin" and target.suffix.lower() == ".app" and target.is_dir()):
        return "JARVIS only opens an approved executable/application file; this target is not a file."
    try:
        if platform.system() == "Windows":
            os.startfile(str(target))  # type: ignore[attr-defined]
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(target)], close_fds=True)
        else:
            if not os.access(target, os.X_OK) and target.suffix.lower() != ".desktop":
                return f"‘{name}’ is not marked executable. Choose the application launcher or executable in Settings."
            if target.suffix.lower() == ".desktop":
                subprocess.Popen(["gtk-launch", target.stem], close_fds=True)
            else:
                subprocess.Popen([str(target)], close_fds=True)
    except Exception as exc:
        return f"I could not open ‘{name}’: {exc}"
    return f"Opened approved app ‘{name}’."


def add_approved_app(settings: dict[str, Any], name: str, path: str | Path) -> None:
    label = " ".join(name.strip().lower().split())
    if not label or len(label) > 60:
        raise ValueError("Give the approved app a name of 1–60 characters.")
    target = Path(path).expanduser().resolve(strict=True)
    if not target.is_file() and not (platform.system() == "Darwin" and target.suffix.lower() == ".app" and target.is_dir()):
        raise ValueError("Choose a single executable or application file, not a folder.")
    if target.suffix.lower() in {".py", ".pyw", ".sh", ".bash", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".html"}:
        raise ValueError("Script and document files cannot be approved as desktop applications.")
    apps = settings.setdefault("approved_apps", {})
    if not isinstance(apps, dict):
        apps = settings["approved_apps"] = {}
    apps[label] = str(target)
