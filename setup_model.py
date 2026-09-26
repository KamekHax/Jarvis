#!/usr/bin/env python3
"""Download and safely unpack the small English Vosk model for offline use."""
from __future__ import annotations

import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from app_paths import user_data_root

ROOT = user_data_root() if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
MODELS = ROOT / "models"
MODEL_NAME = "vosk-model-small-en-us-0.15"
URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"


def safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    base = destination.resolve()
    for member in archive.infolist():
        # Archives use POSIX path separators; reject absolute paths and traversal.
        name = PurePosixPath(member.filename)
        if name.is_absolute() or ".." in name.parts:
            raise RuntimeError(f"Unsafe path in model archive: {member.filename}")
        output = (destination / Path(*name.parts)).resolve()
        if output != base and base not in output.parents:
            raise RuntimeError(f"Unsafe path in model archive: {member.filename}")
    archive.extractall(destination)


def main() -> int:
    MODELS.mkdir(parents=True, exist_ok=True)
    target = MODELS / MODEL_NAME
    if target.is_dir():
        print(f"Speech model already installed: {target}")
        return 0
    temp_root = Path(tempfile.mkdtemp(prefix="jarvis-model-"))
    archive_path = temp_root / "model.zip"
    try:
        print("Downloading the Vosk English model (~40 MB). This is a one-time setup step;")
        print("the assistant uses it from disk and does not need internet while running.")
        request = urllib.request.Request(URL, headers={"User-Agent": "JARVIS-Local-Setup/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response, archive_path.open("wb") as out:
            shutil.copyfileobj(response, out)
        with zipfile.ZipFile(archive_path) as archive:
            safe_extract(archive, MODELS)
        if not target.is_dir():
            raise RuntimeError("Download unpacked, but the expected model folder was not found.")
        print(f"Installed offline speech model: {target}")
        return 0
    except Exception as exc:
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        print(f"Model setup failed: {exc}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
