"""Create a per-user launch shortcut for the installed desktop application."""
from __future__ import annotations

import os
import platform
import shlex
import sys
from pathlib import Path


def create_desktop_shortcut(project: Path, python_exe: Path | None = None) -> Path:
    """Create a normal app-menu shortcut; this does not enable login startup."""
    project = Path(project).resolve()
    frozen = bool(getattr(sys, "frozen", False))
    executable = Path(sys.executable if frozen else (python_exe or sys.executable)).resolve()
    if frozen:
        command = [str(executable)]
    else:
        command = [str(executable), str(project / "run.py")]
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
        target = base / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "JARVIS Local.cmd"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f'@echo off\r\nstart "JARVIS Local" "{command[0]}"' +
                          (f' "{command[1]}"' if len(command) > 1 else "") + "\r\n", encoding="utf-8")
    elif system == "Darwin":
        target = Path.home() / "Applications" / "JARVIS Local.command"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("#!/bin/sh\nexec " + shlex.join(command) + "\n", encoding="utf-8")
        target.chmod(0o755)
    else:
        target = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "applications" / "jarvis-local.desktop"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("[Desktop Entry]\nType=Application\nName=JARVIS Local\n" +
                          f"Exec={shlex.join(command)}\nTerminal=false\nCategories=Utility;\n", encoding="utf-8")
        target.chmod(0o755)
    return target
