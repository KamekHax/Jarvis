"""One-command JARVIS installer with cross-platform Python discovery.

Run with any available Python 3 interpreter:
    python installer.py
    python installer.py --without-chat
"""
from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import venv
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent
MIN_PYTHON = (3, 10)


def _version_at(executable: Path) -> tuple[int, int, int] | None:
    try:
        result = subprocess.run(
            [str(executable), "-c", "import sys; print('%s.%s.%s' % sys.version_info[:3])"],
            capture_output=True, text=True, timeout=4, check=False,
        )
        if result.returncode:
            return None
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", result.stdout)
        if not match:
            return None
        version = tuple(map(int, match.groups()))
        return version  # type: ignore[return-value]
    except (OSError, subprocess.TimeoutExpired):
        return None


def _unique(paths: Iterable[Path]) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        try:
            resolved = path.expanduser().resolve()
            key = os.path.normcase(str(resolved))
            if key not in seen and resolved.is_file():
                seen.add(key)
                found.append(resolved)
        except OSError:
            continue
    return found


def _quick_candidates() -> list[Path]:
    candidates: list[Path] = []
    if sys.executable:
        candidates.append(Path(sys.executable))
    home = Path.home()

    # Search all names currently reachable from PATH, not only the first match.
    for name in ("python3", "python", "python3.13", "python3.12", "python3.11", "python3.10"):
        located = shutil.which(name)
        if located:
            candidates.append(Path(located))

    system = platform.system()
    if system == "Windows":
        launcher = shutil.which("py")
        if launcher:
            try:
                output = subprocess.run([launcher, "-0p"], capture_output=True, text=True,
                                        timeout=8, check=False).stdout
                for line in output.splitlines():
                    match = re.search(r"([A-Za-z]:\\[^\r\n]*?python(?:w)?\.exe)", line, re.I)
                    if match:
                        candidates.append(Path(match.group(1)))
            except (OSError, subprocess.TimeoutExpired):
                pass
        candidates.extend(_windows_registry_candidates())
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        candidates.extend(local.glob("Programs/Python/Python*/python.exe"))
        user_profile = Path(os.environ.get("USERPROFILE", home))
        candidates.extend(user_profile.glob(".pyenv/pyenv-win/versions/*/python.exe"))
        candidates.extend(user_profile.glob("scoop/apps/python/current/python.exe"))
        for conda in (user_profile / "miniconda3", user_profile / "anaconda3", user_profile / "mambaforge"):
            candidates.extend((conda / relative) for relative in (Path("python.exe"), Path("Scripts/python.exe")))
        for base in (Path(os.environ.get("ProgramFiles", "C:/Program Files")),
                     Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))):
            candidates.extend(base.glob("Python*/python.exe"))
    elif system == "Darwin":
        candidates.extend([
            Path("/opt/homebrew/bin/python3"), Path("/usr/local/bin/python3"),
            Path("/Library/Frameworks/Python.framework/Versions/Current/bin/python3"),
        ])
        candidates.extend(Path("/Library/Frameworks/Python.framework/Versions").glob("*/bin/python3"))
        candidates.extend(home.glob(".pyenv/versions/*/bin/python*"))
        candidates.extend(home.glob(".asdf/installs/python/*/bin/python*"))
        candidates.extend(home.glob(".conda/envs/*/bin/python*"))
        candidates.extend(Path("/usr/local/opt").glob("python*/bin/python3*"))
    else:
        for path in ("/usr/bin/python3", "/usr/local/bin/python3", "/bin/python3", "/opt/python/bin/python3"):
            candidates.append(Path(path))
        candidates.extend(home.glob(".local/bin/python*"))
        candidates.extend(home.glob(".pyenv/versions/*/bin/python*"))
        candidates.extend(home.glob(".asdf/installs/python/*/bin/python*"))
        candidates.extend(home.glob(".conda/envs/*/bin/python*"))
        candidates.extend(home.glob("miniconda3/bin/python*"))
        candidates.extend(home.glob("anaconda3/bin/python*"))
        candidates.extend(Path("/opt/conda/bin").glob("python*"))
    return _unique(candidates)


def _windows_registry_candidates() -> list[Path]:
    if platform.system() != "Windows":
        return []
    try:
        import winreg
    except ImportError:
        return []
    paths: list[Path] = []
    hives = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)
    views = [0]
    if hasattr(winreg, "KEY_WOW64_64KEY"):
        views.extend([winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY])
    for hive in hives:
        for view in set(views):
            try:
                root = winreg.OpenKey(hive, r"Software\Python\PythonCore", 0, winreg.KEY_READ | view)
            except OSError:
                continue
            try:
                for index in range(winreg.QueryInfoKey(root)[0]):
                    version = winreg.EnumKey(root, index)
                    for subkey in (version + r"\InstallPath", version + r"\InstallPath\ExecutablePath"):
                        try:
                            key = winreg.OpenKey(root, subkey)
                            value = winreg.QueryValue(key, None)
                            candidate = Path(value)
                            if candidate.is_dir():
                                candidate /= "python.exe"
                            paths.append(candidate)
                        except OSError:
                            continue
            finally:
                winreg.CloseKey(root)
    return paths


def _scan_roots() -> list[Path]:
    home = Path.home()
    system = platform.system()
    if system == "Windows":
        roots: list[Path] = []
        # Search attached local drive roots. os.walk ignores inaccessible folders.
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = Path(f"{letter}:\\")
            if drive.exists():
                roots.append(drive)
        return roots
    if system == "Darwin":
        return [home, Path("/Applications"), Path("/Library/Frameworks"), Path("/opt"), Path("/usr/local")]
    return [home, Path("/opt"), Path("/usr/local")]


SKIP_DIRS = {
    ".git", ".cache", "node_modules", "site-packages", "dist-packages", "__pycache__",
    "windows", "winsxs", "system volume information", "$recycle.bin", "proc", "sys", "dev",
}
PYTHON_NAMES = {"python", "python.exe", "pythonw.exe", "python3", "python3.exe", "python3.10",
                "python3.11", "python3.12", "python3.13"}


def _deep_candidates(seconds: int = 45) -> list[Path]:
    """Bounded recursive fallback for installations outside PATH and common folders."""
    deadline = time.monotonic() + max(1, seconds)
    matches: list[Path] = []
    seen: set[str] = set()

    def on_error(_error: OSError) -> None:
        return

    for root in _scan_roots():
        if time.monotonic() >= deadline:
            break
        print(f"Searching for Python under {root} (up to {seconds}s)…", flush=True)
        for current, directories, files in os.walk(root, topdown=True, onerror=on_error, followlinks=False):
            if time.monotonic() >= deadline:
                return _unique(matches)
            directories[:] = [name for name in directories if name.lower() not in SKIP_DIRS]
            for filename in files:
                lower = filename.lower()
                if lower in PYTHON_NAMES or re.fullmatch(r"python3\.\d+(?:\.exe)?", lower):
                    candidate = Path(current) / filename
                    key = os.path.normcase(str(candidate))
                    if key not in seen:
                        seen.add(key)
                        version = _version_at(candidate)
                        if version and version[:2] >= MIN_PYTHON:
                            return [candidate]
                        if version:
                            matches.append(candidate)
    return _unique(matches)


def discover_python(search_seconds: int = 45) -> tuple[Path | None, list[str]]:
    """Find an executable Python >=3.10, checking active runtime, PATH, and common locations.

    A recursive scan of user/app folders is used only if quick checks do not find a suitable
    interpreter, avoiding a long scan on typical systems.
    """
    diagnostics: list[str] = []
    candidates = _quick_candidates()
    for candidate in candidates:
        version = _version_at(candidate)
        if version is None:
            diagnostics.append(f"Could not run {candidate}")
        elif version[:2] >= MIN_PYTHON:
            return candidate, diagnostics
        else:
            diagnostics.append(f"Python {version[0]}.{version[1]} is too old at {candidate}; need 3.10+")

    # No suitable interpreter found in the runtime, PATH, registry, or conventional installs.
    for candidate in _deep_candidates(search_seconds):
        version = _version_at(candidate)
        if version and version[:2] >= MIN_PYTHON:
            return candidate, diagnostics
        if version:
            diagnostics.append(f"Python {version[0]}.{version[1]} is too old at {candidate}")
    return None, diagnostics


def venv_python(environment: Path) -> Path:
    if platform.system() == "Windows":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def install(with_chat: bool = True, skip_speech_model: bool = False,
            search_seconds: int = 45, refresh: bool = False, launch: bool = False) -> int:
    environment = ROOT / ".venv"
    python = venv_python(environment)
    existing_version = _version_at(python) if python.is_file() else None

    if refresh or existing_version is None or existing_version[:2] < MIN_PYTHON:
        interpreter, diagnostics = discover_python(search_seconds)
        if interpreter is None:
            print("No Python 3.10+ interpreter found. Install Python 3.10 or newer and rerun this installer.", file=sys.stderr)
            for item in diagnostics[-10:]:
                print(f"  {item}", file=sys.stderr)
            return 2
        version = _version_at(interpreter)
        print(f"Using Python {version[0]}.{version[1]}.{version[2]} at: {interpreter}")
        if environment.exists():
            print(f"Rebuilding virtual environment at {environment}")
            shutil.rmtree(environment)
        if Path(sys.executable).resolve() == interpreter.resolve():
            try:
                venv.EnvBuilder(with_pip=True, clear=False, upgrade_deps=False).create(str(environment))
            except Exception as exc:
                print(f"Could not create the project virtual environment: {exc}", file=sys.stderr)
                return 3
        else:
            result = subprocess.run([str(interpreter), "-m", "venv", str(environment)], check=False)
            if result.returncode:
                return result.returncode

    if not python.is_file():
        print(f"Virtual environment Python was not created at {python}", file=sys.stderr)
        return 3

    command = [str(python), str(ROOT / "bootstrap.py")]
    if with_chat:
        command.append("--with-chat")
    else:
        command.append("--without-chat")
    if skip_speech_model:
        command.append("--skip-speech-model")
    print("Installing JARVIS dependencies and downloading configured local models…", flush=True)
    try:
        result = subprocess.run(command, cwd=ROOT, check=False)
    except OSError as exc:
        print(f"Could not start the Python setup: {exc}", file=sys.stderr)
        return 4
    if result.returncode:
        print("Setup did not finish. Rerun installer.py to retry; completed downloads are kept.", file=sys.stderr)
        return result.returncode
    print("\nJARVIS is ready. Start the desktop app with:")
    print(f"  {python} {ROOT / 'run.py'}")
    try:
        from desktop_shortcuts import create_desktop_shortcut
        shortcut = create_desktop_shortcut(ROOT, python_exe=python)
        print(f"Created launcher shortcut: {shortcut}")
    except Exception as exc:
        print(f"Could not create a desktop shortcut (you can still use the command above): {exc}")
    if launch:
        print("Opening the JARVIS desktop interface…")
        launched = subprocess.run([str(python), str(ROOT / "run.py")], cwd=ROOT, check=False)
        return launched.returncode
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automatically find Python and install JARVIS Local")
    chat = parser.add_mutually_exclusive_group()
    chat.add_argument("--with-chat", dest="with_chat", action="store_true", default=True,
                      help="download and install the ~1.93 GB local chat model (default)")
    chat.add_argument("--without-chat", dest="with_chat", action="store_false",
                      help="skip the large local chat model download")
    parser.add_argument("--skip-speech-model", action="store_true", help="install packages only; skip Vosk model download")
    parser.add_argument("--search-seconds", type=int, default=45,
                        help="time budget for searching folders if no Python is found in common places (default: 45)")
    parser.add_argument("--refresh", action="store_true", help="rebuild the project's virtual environment")
    parser.add_argument("--launch", action="store_true", help="open the desktop interface when setup is complete")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return install(args.with_chat, args.skip_speech_model, args.search_seconds, args.refresh, args.launch)


if __name__ == "__main__":
    raise SystemExit(main())
