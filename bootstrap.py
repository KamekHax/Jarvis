#!/usr/bin/env python3
"""Python-only dependency and model bootstrap for JARVIS Local."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install JARVIS Python dependencies and offline models")
    chat = parser.add_mutually_exclusive_group()
    chat.add_argument("--with-chat", dest="with_chat", action="store_true",
                      help="install llama-cpp-python and download the ~1.93 GB GGUF chat model")
    chat.add_argument("--without-chat", dest="with_chat", action="store_false",
                      help="skip conversational model setup")
    parser.set_defaults(with_chat=False)
    parser.add_argument("--skip-speech-model", action="store_true",
                        help="do not download the offline Vosk speech model")
    args = parser.parse_args()

    if sys.prefix == sys.base_prefix:
        print("Tip: use a virtual environment first: python -m venv .venv")
        print("Continuing in the current Python environment.")

    try:
        run([sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])
        if args.with_chat:
            run([sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements-chat.txt")])
        if not args.skip_speech_model:
            from setup_model import main as setup_speech_model
            status = setup_speech_model()
            if status:
                return status
        if args.with_chat:
            from download_local_model import main as download_chat_model
            status = download_chat_model()
            if status:
                return status

        config_path = ROOT / "config.json"
        if config_path.exists():
            config = json.loads(config_path.read_text(encoding="utf-8"))
        else:
            config = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
        config["use_local_chat"] = bool(args.with_chat)
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    except subprocess.CalledProcessError as exc:
        print(f"Setup command failed with exit code {exc.returncode}.", file=sys.stderr)
        return exc.returncode or 1
    except Exception as exc:
        print(f"Setup failed: {exc}", file=sys.stderr)
        return 1

    print("\nSetup complete. Start the assistant with: python run.py")
    if args.with_chat:
        print("Local chat is enabled and runs inside the Python process.")
    else:
        print("Built-in skills are ready. Chat model was skipped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
