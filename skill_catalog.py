"""Reviewed, bundled addons that users may opt to install by explicit command."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re

from app_paths import bundle_root, user_data_root

# SHA-256 pins prevent edited/copied catalog code from being treated as trusted.
# Recompute when a reviewed bundled addon intentionally changes.
CATALOG = {
    "music": {
        "name": "music",
        "description": "Play/pause/skip local audio from one folder you select (requires local playback permission and pygame).",
        "filename": "music_skill.py",
        "sha256": "8e09dda35429aa5ac3771dcaa427bdeec5bcb604f7a86aa5fe0aba247c3cb643",
        "aliases": ("local music", "music player", "local music player"),
    },
}


def list_catalog() -> dict[str, str]:
    return {name: str(info["description"]) for name, info in CATALOG.items()}


def normalize_name(value: str) -> str | None:
    candidate = re.sub(r"\s+", " ", value.strip().casefold())
    for name, info in CATALOG.items():
        aliases = (name, *info["aliases"])
        if candidate in {str(item).casefold() for item in aliases}:
            return name
    return None


def trusted_hashes() -> dict[str, str]:
    return {str(item["filename"]): str(item["sha256"]) for item in CATALOG.values()}


def installed_skills_dir() -> Path:
    return user_data_root() / "data" / "installed_skills"


def install_skill(name: str, destination: Path | None = None) -> tuple[str, Path | None]:
    """Install only a known, bundled, hash-pinned skill. Does not use the internet."""
    key = normalize_name(name)
    if key is None:
        return f"‘{name}’ is not in the bundled addon catalog. Available: {', '.join(CATALOG)}.", None
    info = CATALOG[key]
    source = bundle_root() / "bundled_addons" / str(info["filename"])
    if not source.is_file():
        return f"The bundled {key} addon is missing from this installation.", None
    expected = str(info["sha256"])
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        return f"The bundled {key} addon has no valid integrity pin; installation stopped.", None
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != expected:
        return f"Integrity check failed for the bundled {key} addon; nothing was installed.", None
    target_dir = (destination or installed_skills_dir()).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / str(info["filename"])
    if target.exists():
        current = hashlib.sha256(target.read_bytes()).hexdigest()
        if current != expected:
            return f"An unverified file already exists at {target}; remove it manually before installing this addon.", None
        return f"The {key} addon is already installed and verified.", target
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        temporary.write_bytes(source.read_bytes())
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != expected:
            temporary.unlink(missing_ok=True)
            return f"Integrity check failed while installing {key}; nothing was installed.", None
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return f"Installed the verified local {key} addon. It is ready to enable in Skills; no files or packages were downloaded.", target
