"""Best-effort system-wide hotkeys; falls back cleanly on unsupported desktops."""
from __future__ import annotations

from typing import Callable

MODIFIERS = {
    "ctrl": "ctrl", "control": "ctrl", "alt": "alt", "shift": "shift",
    "cmd": "cmd", "win": "cmd",
}


def parse_shortcut(value: str) -> tuple[list[str], str]:
    pieces = [piece.strip().lower() for piece in value.split("+") if piece.strip()]
    modifiers = [MODIFIERS[item] for item in pieces if item in MODIFIERS]
    keys = [item for item in pieces if item not in MODIFIERS]
    if len(modifiers) != len(set(modifiers)):
        raise ValueError("shortcut contains a duplicate modifier")
    if len(keys) != 1:
        raise ValueError("shortcut needs exactly one final key")
    key = keys[0]
    valid = (len(key) == 1 and key.isalnum()) or key in {
        "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
        "f13", "f14", "f15", "f16", "f17", "f18", "f19", "f20", "f21", "f22", "f23", "f24",
        "space", "escape", "enter", "tab", "home", "end", "insert", "delete",
    }
    if not valid:
        raise ValueError(f"unsupported shortcut key: {key}")
    return modifiers, key


def pynput_combo(value: str) -> str:
    modifiers, key = parse_shortcut(value)
    return "+".join([*(f"<{modifier}>" for modifier in modifiers), key])


def tkinter_sequence(value: str) -> str:
    modifiers, key = parse_shortcut(value)
    names = {"ctrl": "Control", "alt": "Alt", "shift": "Shift", "cmd": "Command"}
    final_key = key.upper() if key.startswith("f") else key
    return "<" + "-".join([*(names[item] for item in modifiers), final_key]) + ">"


class GlobalHotkeys:
    def __init__(self, actions: dict[str, tuple[str, Callable[[], None]]]) -> None:
        self.listener = None
        self.error: str | None = None
        try:
            from pynput import keyboard
            mapping = {}
            for combo, action in actions.values():
                try:
                    mapping[pynput_combo(combo)] = action
                except ValueError as exc:
                    self.error = str(exc)
            if not mapping:
                return
            self.listener = keyboard.GlobalHotKeys(mapping)
            self.listener.start()
        except Exception as exc:
            self.error = str(exc)

    def stop(self) -> None:
        if self.listener is not None:
            try:
                self.listener.stop()
            except Exception:
                pass
