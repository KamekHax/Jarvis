"""Permission-gated launch of explicitly allow-listed desktop apps."""
from __future__ import annotations
import re
from permissions import launch_approved_app


def handle(text: str, context: dict) -> str | None:
    match = re.match(r"^(?:open|launch|start) (?:the )?app\s+(.+?)\s*[.!?]*$", text.strip(), re.I)
    if not match:
        return None
    return launch_approved_app(context.get("permissions", {}), match.group(1))


def matches(text: str) -> bool:
    return re.match(r"^(?:open|launch|start) (?:the )?app\s+.+?\s*[.!?]*$", text.strip(), re.I) is not None


def register(manager) -> None:
    manager.register("app_control", "Open only named, allow-listed desktop applications when the permission is enabled.", handle,
                     ("Open app Calculator", "Launch app VS Code"),
                     permissions=("allow_app_launching",), matcher=matches)
