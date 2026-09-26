"""Local-only playlist playback. No streaming services, downloads, or arbitrary paths."""
from __future__ import annotations

from pathlib import Path
import threading
from typing import Callable

AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac"}


class LocalMusicPlayer:
    def __init__(self, music_folder: str | Path = "") -> None:
        self.music_folder = Path(music_folder).expanduser() if music_folder else None
        self._pygame = None
        self._lock = threading.RLock()
        self._playlist: list[Path] = []
        self._index = -1

    def set_folder(self, folder: str | Path) -> None:
        if not str(folder).strip():
            with self._lock:
                self.music_folder = None
                self._playlist = []
                self._index = -1
            return
        target = Path(folder).expanduser().resolve(strict=True)
        if not target.is_dir():
            raise ValueError("Choose an existing local music folder.")
        with self._lock:
            self.music_folder = target
            self._playlist = []
            self._index = -1

    def _load_library(self) -> None:
        if self.music_folder is None or not self.music_folder.exists():
            raise RuntimeError("Choose a local music folder in Settings first.")
        base = self.music_folder.resolve(strict=True)
        tracks = []
        for item in sorted(base.iterdir(), key=lambda path: path.name.casefold()):
            try:
                target = item.resolve(strict=True)
                if target.parent != base or not target.is_file() or target.suffix.casefold() not in AUDIO_EXTENSIONS:
                    continue
                tracks.append(target)
            except (OSError, RuntimeError):
                continue
        if not tracks:
            raise RuntimeError("No supported audio files were found directly in the selected music folder.")
        self._playlist = tracks

    def _engine(self):
        if self._pygame is None:
            try:
                import pygame
                pygame.mixer.init()
                self._pygame = pygame
            except Exception as exc:
                raise RuntimeError(f"Local audio playback is unavailable: {exc}") from exc
        return self._pygame

    def play(self, query: str = "") -> str:
        with self._lock:
            if not self._playlist:
                self._load_library()
            query = " ".join(query.strip().casefold().split())
            if query:
                matches = [index for index, track in enumerate(self._playlist)
                           if query in track.stem.casefold()]
                if not matches:
                    return f"I couldn't find ‘{query}’ in the selected local music folder."
                self._index = matches[0]
            elif self._index < 0:
                self._index = 0
            track = self._playlist[self._index]
            engine = self._engine()
            try:
                engine.mixer.music.load(str(track))
                engine.mixer.music.play()
            except Exception as exc:
                raise RuntimeError(f"Could not play {track.name}: {exc}") from exc
            return f"Playing {track.stem} from your local music folder."

    def pause(self) -> str:
        with self._lock:
            if self._pygame is None or not self._pygame.mixer.get_init():
                return "Nothing is playing from the local music library."
            self._pygame.mixer.music.pause()
            return "Paused local music."

    def resume(self) -> str:
        with self._lock:
            if self._pygame is None or not self._playlist or self._index < 0:
                return self.play()
            self._pygame.mixer.music.unpause()
            return f"Resumed {self._playlist[self._index].stem}."

    def stop(self) -> str:
        with self._lock:
            if self._pygame is not None and self._pygame.mixer.get_init():
                self._pygame.mixer.music.stop()
            return "Stopped local music."

    def next(self) -> str:
        with self._lock:
            if not self._playlist:
                self._load_library()
            self._index = (self._index + 1) % len(self._playlist)
            return self.play()

    def close(self) -> None:
        with self._lock:
            if self._pygame is not None and self._pygame.mixer.get_init():
                try:
                    self._pygame.mixer.music.stop()
                    self._pygame.mixer.quit()
                except Exception:
                    pass
