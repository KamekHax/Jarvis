"""Offline unit conversions for everyday measurements."""
from __future__ import annotations
import re

ALIASES = {
    "miles": "mile", "mi": "mile", "kilometers": "km", "kilometres": "km", "kilometer": "km", "kilometre": "km",
    "meters": "m", "metres": "m", "meter": "m", "metre": "m", "feet": "ft", "foot": "ft", "yards": "yd",
    "pounds": "lb", "lbs": "lb", "kilograms": "kg", "kilos": "kg", "grams": "g", "ounces": "oz",
    "celsius": "c", "centigrade": "c", "fahrenheit": "f", "cups": "cup", "milliliters": "ml", "millilitres": "ml",
    "liters": "l", "litres": "l", "gallons": "gal",
}
FACTORS = {
    "mile": ("distance", 1609.344, "m"), "km": ("distance", 1000.0, "m"), "m": ("distance", 1.0, "m"),
    "ft": ("distance", .3048, "m"), "yd": ("distance", .9144, "m"),
    "lb": ("weight", .45359237, "kg"), "kg": ("weight", 1.0, "kg"), "g": ("weight", .001, "kg"), "oz": ("weight", .028349523125, "kg"),
    "ml": ("volume", .001, "l"), "l": ("volume", 1.0, "l"), "cup": ("volume", .2365882365, "l"), "gal": ("volume", 3.785411784, "l"),
    "c": ("temperature", 1, "c"), "f": ("temperature", 1, "f"),
}
PATTERN = re.compile(r"^(?:convert\s+)?(-?\d+(?:\.\d+)?)\s*([a-zA-Z]+)\s+(?:to|in|into)\s+([a-zA-Z]+)\??$", re.I)


def handle(text: str, _context: dict) -> str | None:
    match = PATTERN.match(text.strip())
    if not match:
        return None
    value = float(match.group(1))
    source = ALIASES.get(match.group(2).lower(), match.group(2).lower())
    target = ALIASES.get(match.group(3).lower(), match.group(3).lower())
    if source not in FACTORS or target not in FACTORS:
        return None
    src_kind, src_factor, _ = FACTORS[source]
    dst_kind, dst_factor, _ = FACTORS[target]
    if src_kind != dst_kind:
        return "Those are different measurement types. Try distance, weight, volume, or temperature conversions."
    if src_kind == "temperature":
        result = (value * 9 / 5 + 32) if source == "c" and target == "f" else (value - 32) * 5 / 9 if source == "f" and target == "c" else value
    else:
        result = value * src_factor / dst_factor
    return f"{value:g} {source} is approximately {result:.4g} {target}."


def register(manager) -> None:
    manager.register("conversion", "Convert common local units of distance, mass, volume, and temperature.", handle,
                     ("Convert 12 miles to km", "Convert 20 Celsius to Fahrenheit"))
