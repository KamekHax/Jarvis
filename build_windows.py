"""Build a Windows onedir distribution with Python embedded (Windows host required)."""
from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def bundled_assets() -> list[tuple[Path, str]]:
    assets: list[tuple[Path, str]] = [(ROOT / "config.example.json", ".")]
    for name in ("LICENSE", "TERMS_OF_USE.md", "CONTRIBUTING.md",
                 "THIRD_PARTY_NOTICES.md", "README.md"):
        policy_file = ROOT / name
        if policy_file.is_file():
            assets.append((policy_file, "."))
    skills = ROOT / "skills"
    if skills.is_dir():
        assets.extend((path, "skills") for path in sorted(skills.glob("*_skill.py")))
    addons = ROOT / "bundled_addons"
    if addons.is_dir():
        assets.extend((path, "bundled_addons") for path in sorted(addons.glob("*_skill.py")))
    models = ROOT / "models"
    if models.is_dir():
        for model in sorted(models.iterdir()):
            if model.name.endswith(".gguf") or model.name.startswith("vosk-model-"):
                assets.append((model, "models"))
    return assets


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a Windows JARVIS folder with a standalone EXE")
    parser.add_argument("--dry-run", action="store_true", help="list planned packaged resources on any OS")
    args = parser.parse_args()
    assets = bundled_assets()
    for source, target in assets:
        print(f"Bundle {source} -> {target}")
    chat_model = any(path.suffix == ".gguf" for path, _ in assets)
    speech_model = any(path.is_dir() and path.name.startswith("vosk-model-") for path, _ in assets)
    if not chat_model:
        print("NOTE: chat GGUF not found; the packaged app will show an in-app install/retry control.")
    if not speech_model:
        print("NOTE: Vosk model not found; voice setup can be repaired from Settings.")
    if args.dry_run:
        return 0
    if platform.system() != "Windows":
        print("A native Windows executable must be built on Windows. Run build_windows.bat there.", file=sys.stderr)
        return 2

    try:
        import PyInstaller.__main__
    except ImportError:
        print("Install PyInstaller inside .venv with: pip install -r requirements-build.txt", file=sys.stderr)
        return 3
    arguments = [
        str(ROOT / "run.py"), "--noconfirm", "--clean", "--onedir", "--windowed",
        "--name", "JARVIS", "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build" / "pyinstaller"),
        "--specpath", str(ROOT / "build"),
        "--collect-all", "vosk", "--collect-all", "sounddevice",
        "--collect-all", "pyttsx3", "--collect-all", "pynput",
        "--collect-all", "llama_cpp", "--collect-all", "pygame",
        "--collect-all", "onnxruntime", "--collect-all", "ttstokenizer",
        "--collect-all", "nltk", "--collect-all", "anyascii", "--collect-all", "inflect",
        "--hidden-import", "_tkinter", "--hidden-import", "jarvis_ui",
        "--hidden-import", "skill_manager", "--hidden-import", "memory",
        "--hidden-import", "desktop_settings", "--hidden-import", "hud",
        "--hidden-import", "app_paths", "--hidden-import", "permissions",
        "--hidden-import", "themes", "--hidden-import", "theme_manager",
        "--hidden-import", "voices", "--hidden-import", "setup_model",
        "--hidden-import", "download_local_model",
        "--hidden-import", "internet_search", "--hidden-import", "music_player",
        "--hidden-import", "voicepacks", "--hidden-import", "onnxruntime",
        "--hidden-import", "skill_catalog", "--hidden-import", "desktop_shortcuts",
    ]
    separator = ";"  # PyInstaller --add-data delimiter on Windows.
    for source, destination in assets:
        arguments.extend(["--add-data", f"{source}{separator}{destination}"])
    PyInstaller.__main__.run(arguments)
    print(f"Built folder: {ROOT / 'dist' / 'JARVIS'}")
    print("Distribute the full folder, not only JARVIS.exe; it contains the embedded Python runtime and dependencies.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
