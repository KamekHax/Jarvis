"""Command-only installation for reviewed, bundled local addon modules."""
from __future__ import annotations

import re

INSTALL = re.compile(r"^(?:please\s+)?(?:install|add)\s+(?:the\s+)?skill\s+(.+)$", re.I)
LIST = {"list installable skills", "what can you install", "show addon catalog"}


def match(text: str) -> bool:
    normalized = " ".join(text.strip().casefold().split())
    return normalized in LIST or bool(INSTALL.match(normalized))


def handle(text: str, context: dict) -> str | None:
    normalized = " ".join(text.strip().casefold().split())
    action = context.get("actions", {}).get("install_skill")
    if normalized in LIST:
        if not context.get("permissions", {}).get("allow_skill_installation", False):
            return "Skill installation is disabled. Enable ‘Allow command-installed bundled skills’ in Security & permissions to see the local catalog. Nothing was installed."
        catalog = context.get("catalog", {})
        if not catalog:
            return "No optional bundled skills are available."
        return "Optional local skills (install only by command): " + "; ".join(
            f"{name}: {description}" for name, description in catalog.items()
        ) + ". Say ‘install skill music’ to add one."
    found = INSTALL.match(text.strip())
    if not found:
        return None
    if not context.get("permissions", {}).get("allow_skill_installation", False):
        return "Skill installation is disabled. Enable ‘Allow command-installed bundled skills’ in Security & permissions first; I did not install anything."
    if not callable(action):
        return "The local addon installer is unavailable. Open the Skills panel."
    name = re.sub(r"\s+", " ", found.group(1).strip(" .?!,;"))
    return action(name)


def register(manager) -> None:
    manager.register("catalog", "List and install reviewed bundled add-ons only when explicitly commanded.",
                     handle, ("List installable skills", "Install skill music"),
                     permissions=("allow_skill_installation",), matcher=match)
