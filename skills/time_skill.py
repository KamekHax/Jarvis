"""Built-in local date and time skill."""
from __future__ import annotations

import datetime as dt
import re


def handle(text: str, _context: dict) -> str | None:
    phrase = re.sub(r"[^\w\s]", " ", text.lower()).strip()
    phrase = re.sub(r"\s+", " ", phrase)
    if phrase in {"time", "what time is it", "tell me the time", "what is the time"}:
        return dt.datetime.now().astimezone().strftime("It is %I:%M %p.")
    if phrase in {"date", "what is the date", "what s the date", "what day is it", "tell me the date"}:
        today = dt.datetime.now().astimezone()
        return f"Today is {today:%A}, {today:%B} {today.day}, {today:%Y}."
    return None


def register(manager) -> None:
    manager.register("time", "Tell the current local time and date.", handle,
                     ("What time is it?", "What is the date?"))
