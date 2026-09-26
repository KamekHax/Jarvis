#!/usr/bin/env python3
"""Download a GGUF chat model for direct in-process llama-cpp-python inference."""
from __future__ import annotations

import os
import re
import sys
import time
import urllib.request
from pathlib import Path
from app_paths import user_data_root

ROOT = user_data_root() if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
MODELS = ROOT / "models"
FILENAME = "Qwen2.5-3B-Instruct-Q4_K_M.gguf"
MIN_MODEL_BYTES = 1_700_000_000
PROGRESS_CALLBACK = None
URL = (
    "https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/"
    "Qwen2.5-3B-Instruct-Q4_K_M.gguf?download=true"
)


def main() -> int:
    MODELS.mkdir(parents=True, exist_ok=True)
    target = MODELS / FILENAME
    if target.is_file() and target.stat().st_size > MIN_MODEL_BYTES:
        print(f"Local chat model already installed: {target}")
        return 0

    temporary = target.with_suffix(target.suffix + ".part")
    try:
        print("Downloading Qwen2.5 3B Q4_K_M GGUF (about 1.93 GB).")
        print("This is a one-time setup download; inference runs locally inside Python.")
        offset = temporary.stat().st_size if temporary.exists() else 0
        headers = {"User-Agent": "JARVIS-Local-Setup/1.0"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
            print(f"Resuming from {offset / 1e9:.2f} GB.")
        request = urllib.request.Request(URL, headers=headers)
        with urllib.request.urlopen(request, timeout=90) as response:
            status = getattr(response, "status", response.getcode())
            if offset and status != 206:
                print("The server did not support resume; restarting the model download.")
                offset = 0
            content_range = response.headers.get("Content-Range", "")
            match = re.fullmatch(r"bytes\s+\d+-\d+/(\d+)", content_range)
            total = int(match.group(1)) if match else int(response.headers.get("Content-Length", "0") or 0) + offset
            downloaded = offset
            last_report = time.monotonic()
            with temporary.open("ab" if offset else "wb") as out:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        percent = downloaded / total
                        print(f"\rDownloaded {percent:.0%} ({downloaded / 1e9:.2f} GB)", end="", flush=True)
                        if PROGRESS_CALLBACK and (time.monotonic() - last_report >= .5 or downloaded >= total):
                            PROGRESS_CALLBACK(f"Downloading local AI model · {percent:.0%}")
                            last_report = time.monotonic()
        print()
        actual_size = temporary.stat().st_size
        if total and actual_size != total:
            raise RuntimeError(f"The download is incomplete ({actual_size} of {total} bytes). Rerun setup to resume.")
        if actual_size < MIN_MODEL_BYTES:
            raise RuntimeError("Downloaded file is unexpectedly small; refusing to install it.")
        os.replace(temporary, target)
        print(f"Installed local chat model: {target}")
        return 0
    except Exception as exc:
        print(f"Model download failed: {exc}", file=sys.stderr)
        if temporary.exists():
            print(f"Partial data is kept at {temporary}; retry to resume.", file=sys.stderr)
        print("You can retry later with: python download_local_model.py", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
