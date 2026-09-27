"""Opt-in, checksum-pinned download manager for local Kokoro ONNX voices."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

MODEL_REVISION = "95648bdb895e6016db92fcce020f5378d011d9bc"
MODEL_BASE = f"https://huggingface.co/NeuML/kokoro-int8-onnx/resolve/{MODEL_REVISION}"
VOICE_PACK_FILES = {
    "model": {
        "filename": "model.onnx",
        "url": f"{MODEL_BASE}/model.onnx?download=true",
        "size": 92_360_686,
        "sha256": "03e2815f4be9c8289b3b0919f40f5857acd24cfd121ca258cf042d309ee3a0cf",
    },
    "voices": {
        "filename": "voices.json",
        "url": f"{MODEL_BASE}/voices.json?download=true",
        "size": 54_060_439,
        "sha256": "dc24670e8333cb30990726c5d99e991afc14645139d1a9d2d1858d4fba08df05",
    },
}
VOICE_CHOICES = {
    "American · Default": ("af", "en-us"),
    "American · Bella": ("af_bella", "en-us"),
    "American · Nicole": ("af_nicole", "en-us"),
    "American · Sarah": ("af_sarah", "en-us"),
    "American · Sky": ("af_sky", "en-us"),
    "American · Adam": ("am_adam", "en-us"),
    "American · Michael": ("af_michael", "en-us"),
    "British · Emma": ("bf_emma", "en-gb"),
    "British · Isabella": ("bf_isabella", "en-gb"),
    "British · George": ("bm_george", "en-gb"),
    "British · Lewis": ("bm_lewis", "en-gb"),
}
VOICE_LABELS = {voice_id: label for label, (voice_id, _lang) in VOICE_CHOICES.items()}
VOICE_LANGUAGES = {voice_id: lang for _label, (voice_id, lang) in VOICE_CHOICES.items()}


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def voice_pack_paths(folder: Path) -> tuple[Path, Path]:
    return folder / VOICE_PACK_FILES["model"]["filename"], folder / VOICE_PACK_FILES["voices"]["filename"]


def is_voice_pack_installed(folder: Path, *, verify_hashes: bool = False) -> bool:
    model_path, voices_path = voice_pack_paths(folder)
    for path, key in ((model_path, "model"), (voices_path, "voices")):
        metadata = VOICE_PACK_FILES[key]
        if not path.is_file() or path.stat().st_size != metadata["size"]:
            return False
        if verify_hashes and _digest(path) != metadata["sha256"]:
            return False
    return True


def ensure_voice_runtime(runtime_folder: Path) -> None:
    """Load packaged runtime, or install only permissively licensed deps after opt-in."""
    packages_missing = (importlib.util.find_spec("onnxruntime") is None
                        or importlib.util.find_spec("ttstokenizer") is None)
    if packages_missing and getattr(sys, "frozen", False):
        raise RuntimeError("The packaged neural-voice runtime is missing. Repair or reinstall JARVIS.")
    runtime_folder.mkdir(parents=True, exist_ok=True)
    if packages_missing:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
             "--target", str(runtime_folder), "onnxruntime==1.20.1", "ttstokenizer==1.1.0"],
            check=False, timeout=900, capture_output=True, text=True,
        )
        if result.returncode:
            detail = (result.stderr or result.stdout or "").strip()[-1600:]
            raise RuntimeError("Could not install the local voice engine. " + detail)
    if str(runtime_folder) not in sys.path:
        sys.path.insert(0, str(runtime_folder))
    importlib.invalidate_caches()
    if (importlib.util.find_spec("onnxruntime") is None
            or importlib.util.find_spec("ttstokenizer") is None):
        raise RuntimeError("The voice engine installer finished, but its packages could not be loaded.")

    import nltk  # type: ignore
    nltk_data = runtime_folder / "nltk_data"
    nltk_data.mkdir(parents=True, exist_ok=True)
    nltk.data.path[:] = [str(nltk_data)]
    os.environ["NLTK_DATA"] = os.pathsep.join(
        part for part in (str(nltk_data), os.environ.get("NLTK_DATA", "")) if part
    )
    resources = (
        ("cmudict", "corpora/cmudict.zip"),
        ("averaged_perceptron_tagger", "taggers/averaged_perceptron_tagger.zip"),
        ("averaged_perceptron_tagger_eng", "taggers/averaged_perceptron_tagger_eng.zip"),
    )
    for resource_id, resource_path in resources:
        try:
            nltk.data.find(resource_path)
        except LookupError:
            if not nltk.download(resource_id, download_dir=str(nltk_data), quiet=True):
                raise RuntimeError(
                    f"Could not download the required English tokenizer data ({resource_id})."
                )
    if str(nltk_data) not in nltk.data.path:
        nltk.data.path.insert(0, str(nltk_data))


def configure_voice_data(runtime_folder: Path) -> bool:
    """Use cached tokenizer data for later speech; never download during startup or inference."""
    if any(importlib.util.find_spec(name) is None for name in ("onnxruntime", "ttstokenizer", "nltk")):
        return False
    nltk_data = runtime_folder / "nltk_data"
    if not nltk_data.is_dir():
        return False
    import nltk  # type: ignore
    if str(nltk_data) not in nltk.data.path:
        nltk.data.path.insert(0, str(nltk_data))
    existing = os.environ.get("NLTK_DATA", "")
    entries = [str(nltk_data), *(item for item in existing.split(os.pathsep) if item)]
    os.environ["NLTK_DATA"] = os.pathsep.join(dict.fromkeys(entries))
    required = (
        "corpora/cmudict.zip",
        "taggers/averaged_perceptron_tagger.zip",
        "taggers/averaged_perceptron_tagger_eng.zip",
    )
    try:
        for resource in required:
            nltk.data.find(resource)
    except LookupError:
        return False
    return True


def _download_asset(key: str, folder: Path, progress: Callable[[str], None] | None = None) -> Path:
    metadata = VOICE_PACK_FILES[key]
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / metadata["filename"]
    if destination.is_file() and destination.stat().st_size == metadata["size"]:
        if _digest(destination) == metadata["sha256"]:
            return destination
    partial = destination.with_suffix(destination.suffix + ".part")
    partial.unlink(missing_ok=True)
    request = Request(metadata["url"], headers={"User-Agent": "JARVIS-Local/voice-pack"})
    digest = hashlib.sha256()
    downloaded = 0
    try:
        with urlopen(request, timeout=30) as response, partial.open("wb") as output:
            final = urlparse(response.geturl())
            if final.scheme != "https" or not (final.hostname == "hf.co" or str(final.hostname).endswith(".hf.co")):
                raise RuntimeError("Voice download redirected outside the trusted HTTPS host.")
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                downloaded += len(block)
                if downloaded > metadata["size"]:
                    raise RuntimeError("Voice download exceeded the expected file size.")
                digest.update(block)
                output.write(block)
                if progress:
                    progress(f"Downloading local voice files… {downloaded / metadata['size']:.0%}")
        if downloaded != metadata["size"]:
            raise RuntimeError(f"Incomplete voice download: expected {metadata['size']} bytes, received {downloaded}.")
        if digest.hexdigest() != metadata["sha256"]:
            raise RuntimeError("Voice download failed SHA-256 verification; the file was discarded.")
        os.replace(partial, destination)
        return destination
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def download_voice_pack(folder: Path, progress: Callable[[str], None] | None = None) -> tuple[Path, Path]:
    """Fetch the upstream ~146 MB CPU voice pack after an explicit user action."""
    _download_asset("model", folder, progress)
    _download_asset("voices", folder, progress)
    model_path, voices_path = voice_pack_paths(folder)
    if not is_voice_pack_installed(folder, verify_hashes=True):
        raise RuntimeError("The installed local voice pack failed verification.")
    return model_path, voices_path
