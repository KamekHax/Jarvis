"""Bundle the project ZIP into one self-extracting Python setup file."""
from __future__ import annotations

import argparse
import base64
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build JARVIS Local's one-file Python setup script")
    parser.add_argument("archive", type=Path, help="Source project ZIP (normally JARVIS-Local.zip)")
    parser.add_argument("output", type=Path, help="Destination .py file")
    args = parser.parse_args()
    payload = base64.b64encode(args.archive.read_bytes()).decode("ascii")
    chunks = "\n".join(f'    "{payload[i:i + 100]}"' for i in range(0, len(payload), 100))
    script = f'''#!/usr/bin/env python3
"""JARVIS Local — self-extracting, one-file Python setup.

Run: python {args.output.name} [--without-chat] [--no-launch]
Requires Python 3.10+ to start. Application files and all setup scripts are embedded below.
"""
from __future__ import annotations
import argparse
import base64
import io
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

BUNDLE = (\n{chunks}\n)


def extract_project(destination: Path) -> Path:
    destination = destination.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    data = base64.b64decode("".join(BUNDLE))
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        base = destination.resolve()
        for entry in bundle.infolist():
            path = PurePosixPath(entry.filename)
            parts = path.parts[1:] if path.parts and path.parts[0] == "jarvis-local" else path.parts
            if path.is_absolute() or ".." in parts:
                raise RuntimeError(f"Unsafe path in embedded app: {{entry.filename}}")
            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise RuntimeError(f"Refusing symbolic link in embedded app: {{entry.filename}}")
            if not parts:
                continue
            output = (destination / Path(*parts)).resolve()
            if output != base and base not in output.parents:
                raise RuntimeError(f"Unsafe path in embedded app: {{entry.filename}}")
            if entry.is_dir():
                output.mkdir(parents=True, exist_ok=True)
                continue
            output.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(entry) as source, output.open("wb") as target:
                shutil.copyfileobj(source, target)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Set up JARVIS Local from this single Python file")
    chat = parser.add_mutually_exclusive_group()
    chat.add_argument("--with-chat", dest="with_chat", action="store_true",
                      help="download the ~1.93 GB local chat model (default)")
    chat.add_argument("--without-chat", dest="with_chat", action="store_false",
                      help="skip the large local chat model download")
    parser.set_defaults(with_chat=True)
    parser.add_argument("--no-launch", action="store_true", help="install without opening the desktop interface")
    parser.add_argument("--skip-speech-model", action="store_true", help="install Python packages without downloading Vosk")
    parser.add_argument("--extract-only", action="store_true", help="unpack the project but do not install it")
    parser.add_argument("--folder", type=Path, default=Path.home() / "JARVIS-Local",
                        help="project install folder (default: ~/JARVIS-Local)")
    args = parser.parse_args()
    try:
        project = extract_project(args.folder)
    except Exception as exc:
        print(f"Could not unpack JARVIS Local: {{exc}}", file=sys.stderr)
        return 2
    command = [sys.executable, str(project / "installer.py")]
    if args.with_chat:
        command.append("--with-chat")
    else:
        command.append("--without-chat")
    if args.skip_speech_model:
        command.append("--skip-speech-model")
    if not args.no_launch:
        command.append("--launch")
    print(f"JARVIS files extracted to: {{project}}")
    if args.extract_only:
        return 0
    print("Starting automatic Python setup…", flush=True)
    try:
        return subprocess.run(command, cwd=project, check=False).returncode
    except OSError as exc:
        print(f"Could not start setup: {{exc}}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
'''
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(script, encoding="utf-8")
    try:
        args.output.chmod(args.output.stat().st_mode | 0o111)
    except OSError:
        pass
    print(f"Created one-file setup: {args.output} ({args.output.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
