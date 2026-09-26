#!/usr/bin/env python3
"""Python launcher for JARVIS Local's desktop or terminal interface."""
from __future__ import annotations

import sys


def configure_frozen_logging() -> None:
    if not getattr(sys, "frozen", False) or sys.stdout is not None:
        return
    try:
        from app_paths import user_data_root
        log_dir = user_data_root() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        handle = (log_dir / "jarvis.log").open("a", encoding="utf-8", buffering=1)
        sys.stdout = handle
        sys.stderr = handle
    except Exception:
        import os
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")


def main() -> int:
    configure_frozen_logging()
    if "--terminal" in sys.argv:
        sys.argv.remove("--terminal")
        from jarvis import main as terminal_main
        return terminal_main()
    try:
        from jarvis_ui import main as desktop_main
    except ModuleNotFoundError as exc:
        if exc.name == "tkinter":
            print("Tkinter is missing from this Python installation. Install your OS Python Tk package (for Debian/Ubuntu: python3-tk), then run this script again.")
            return 2
        raise
    return desktop_main()


if __name__ == "__main__":
    raise SystemExit(main())
