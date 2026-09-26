"""Local code coaching and permission-gated workspace file saving."""
from __future__ import annotations

import re
from pathlib import Path

SAVE_CODE = re.compile(r"^(?:save|write) (?:the )?(?:last )?(?:code|program|script)(?: as| to)?\s+(.+)$", re.I)


def _extract_code(text: str) -> tuple[str | None, str]:
    match = re.search(r"```([\w+#.-]*)\s*\n(.*?)```", text, re.S)
    return (match.group(1).lower() or None, match.group(2).strip()) if match else (None, "")


def matches(text: str) -> bool:
    return SAVE_CODE.match(text.strip()) is not None


def handle(text: str, context: dict) -> str | None:
    manager = context.get("skills")
    if not manager or "coding" not in manager.enabled:
        return None
    match = SAVE_CODE.match(text.strip())
    if not match:
        return None
    permissions = context.get("permissions", {})
    if not permissions.get("allow_workspace_writes", False):
        return "Saving files is blocked. Enable ‘Allow code writes to workspace’ in Security & permissions first."
    configured = str(permissions.get("workspace_dir", "")).strip()
    if not configured:
        return "Choose a workspace folder in Security & permissions before saving code."
    assistant = context.get("assistant")
    previous = str(getattr(assistant, "last_response", ""))
    language, code = _extract_code(previous)
    if not code:
        return "I couldn't find a fenced code block in my latest reply. Ask me to generate code first, then say ‘save code as filename.py’."
    workspace = Path(configured).expanduser().resolve()
    filename = Path(match.group(1).strip().strip('"\''))
    if filename.is_absolute() or any(part in {"..", "."} for part in filename.parts) or len(filename.parts) != 1:
        return "Use a simple filename inside your chosen workspace; path traversal and absolute paths are blocked."
    if not filename.suffix:
        extension = {"python": ".py", "py": ".py", "javascript": ".js", "typescript": ".ts",
                     "html": ".html", "css": ".css", "json": ".json", "bash": ".sh"}.get(language or "", ".txt")
        filename = filename.with_suffix(extension)
    if filename.suffix.lower() in {".exe", ".dll", ".bat", ".cmd", ".ps1", ".sh"}:
        return "JARVIS won't generate or launch executable scripts automatically. Save source code such as .py, .js, .html, or .txt instead."
    target = (workspace / filename).resolve()
    if target.parent != workspace:
        return "The target must remain inside your selected workspace."
    if target.exists():
        return f"{target.name} already exists. Choose a new filename; JARVIS never overwrites a workspace file."
    workspace.mkdir(parents=True, exist_ok=True)
    target.write_text(code + "\n", encoding="utf-8", newline="\n")
    return f"Saved {target.name} inside your approved workspace. I did not run the code."


def register(manager) -> None:
    manager.register("coding", "Ask the local model for coding help; save fenced source code into an approved workspace.", handle,
                     ("Write a Python function that parses a CSV", "Save the last code as parser.py"),
                     permissions=("allow_workspace_writes",), matcher=matches)
