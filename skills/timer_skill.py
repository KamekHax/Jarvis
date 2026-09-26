"""Simple in-process timers with spoken local alerts."""
from __future__ import annotations
import re

NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
           "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30}
PATTERN = re.compile(r"^(?:set )?(?:a )?timer for ([\w.]+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)(?:\s+(?:to|for)\s+(.+))?\??$", re.I)


def handle(text: str, context: dict) -> str | None:
    normalized = text.strip().lower()
    if normalized in {"stop timer", "cancel timer", "cancel all timers"}:
        callback = context.get("actions", {}).get("cancel_timers")
        return callback() if callback else "Timer cancellation is available in the desktop app."
    match = PATTERN.match(normalized)
    if not match:
        return None
    amount = NUMBERS.get(match.group(1), None)
    try:
        amount = float(match.group(1)) if amount is None else amount
    except ValueError:
        return "Say a timer length as a number, such as ‘set a timer for 5 minutes’."
    if amount <= 0 or amount > 86400:
        return "Choose a timer between 1 second and 24 hours."
    unit = match.group(2).lower()
    seconds = amount * (3600 if unit.startswith(("hour", "hr")) else 60 if unit.startswith(("minute", "min")) else 1)
    callback = context.get("actions", {}).get("set_timer")
    if not callback:
        return "Timers are available in the desktop app."
    label = match.group(3) or f"{amount:g} {unit}"
    return callback(seconds, label.strip())


def register(manager) -> None:
    manager.register("timer", "Set and cancel local spoken timers.", handle,
                     ("Set a timer for 5 minutes", "Cancel all timers"))
