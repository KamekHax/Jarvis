"""Lightweight local Python skill registry for JARVIS.

A skill is a trusted Python module in the skills directory that exposes register(manager).
Skills run in-process and have no implicit network access or external permissions.
"""
from __future__ import annotations

import importlib.util
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

SkillHandler = Callable[[str, dict[str, Any]], str | None]


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    handler: SkillHandler
    examples: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    matcher: Callable[[str], bool] | None = None


class SkillManager:
    def __init__(self, directory: Path | list[Path], enabled: list[str] | None = None,
                 allow_integrations: bool = False,
                 trusted_hashes: dict[str, str] | None = None) -> None:
        if isinstance(directory, (str, Path)):
            self.directories = [Path(directory)]
        else:
            self.directories = [Path(item) for item in directory]
        unique: list[Path] = []
        seen: set[str] = set()
        for item in self.directories:
            resolved = item.resolve()
            if str(resolved) not in seen:
                seen.add(str(resolved))
                unique.append(resolved)
        self.directories = unique
        self.enabled = set(enabled or [])
        self.allow_integrations = bool(allow_integrations)
        self.trusted_hashes = dict(trusted_hashes or {})
        self.skills: dict[str, Skill] = {}
        self.load_errors: list[str] = []
        self._loading_external = False
        self._load()

    def register(self, name: str, description: str, handler: SkillHandler,
                 examples: tuple[str, ...] = (), permissions: tuple[str, ...] = (),
                 matcher: Callable[[str], bool] | None = None) -> None:
        key = name.strip().lower().replace(" ", "_")
        if not key or not key.replace("_", "").isalnum():
            raise ValueError(f"Invalid skill name: {name!r}")
        if key in self.skills:
            raise ValueError(f"A skill named {key!r} is already registered")
        if not callable(handler):
            raise TypeError("skill handler must be callable")
        if self._loading_external:
            permissions = tuple(dict.fromkeys((*permissions, "allow_external_integrations")))
        if permissions and not callable(matcher):
            raise TypeError("permission-scoped skills must define a side-effect-free matcher(text)")
        self.skills[key] = Skill(key, description.strip(), handler, tuple(examples), tuple(permissions), matcher)

    def _load(self) -> None:
        for directory in self.directories:
            directory.mkdir(parents=True, exist_ok=True)
            files = sorted(directory.glob("*_skill.py"))
            if self.allow_integrations:
                files.extend(sorted(directory.glob("*_integration.py")))
            for file in files:
                if directory.name == "installed_skills":
                    expected = self.trusted_hashes.get(file.name)
                    if not expected or hashlib.sha256(file.read_bytes()).hexdigest() != expected:
                        self.load_errors.append(f"{file.name}: missing or invalid bundled-addon integrity pin; skipped")
                        continue
                module_name = f"jarvis_skill_{file.stem}_{abs(hash(str(file.resolve())))}"
                self._loading_external = file.name.endswith("_integration.py")
                try:
                    spec = importlib.util.spec_from_file_location(module_name, file)
                    if spec is None or spec.loader is None:
                        raise ImportError("could not create a module loader")
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    register = getattr(module, "register", None)
                    if not callable(register):
                        raise TypeError("skill module must define register(manager)")
                    register(self)
                except Exception as exc:
                    sys.modules.pop(module_name, None)
                    self.load_errors.append(f"{file.name}: {exc}")
                finally:
                    self._loading_external = False

    def reload(self) -> None:
        """Rescan the skills folder while preserving enablement for still-present plugins."""
        previously_enabled = set(self.enabled)
        self.skills.clear()
        self.load_errors.clear()
        self._load()
        self.enabled = previously_enabled.intersection(self.skills)

    def list_skills(self) -> list[dict[str, Any]]:
        return [
            {"name": skill.name, "description": skill.description,
             "examples": skill.examples, "enabled": skill.name in self.enabled,
             "permissions": skill.permissions}
            for skill in self.skills.values()
        ]

    def set_enabled(self, name: str, enabled: bool) -> None:
        key = name.strip().lower().replace(" ", "_")
        if key not in self.skills:
            raise KeyError(f"Unknown skill: {name}")
        if enabled:
            self.enabled.add(key)
        else:
            self.enabled.discard(key)

    def handle(self, text: str, context: dict[str, Any] | None = None) -> str | None:
        shared = context or {}
        for name, skill in self.skills.items():
            if name in self.enabled:
                if skill.permissions:
                    try:
                        matched = bool(skill.matcher and skill.matcher(text))
                    except Exception as exc:
                        self.load_errors.append(f"{name} permission matcher: {exc}")
                        continue
                    if not matched:
                        continue
                permissions = shared.get("permissions", {})
                missing = [permission for permission in skill.permissions
                           if not permissions.get(permission, False)]
                if missing:
                    if name == "app_control":
                        return "App launching is blocked. Enable ‘Allow launching approved apps’ in Security & permissions."
                    if "allow_internet_search" in missing:
                        return "Online search is off. Enable ‘Allow explicitly requested web searches’ in Settings, then ask again. I did not send this query anywhere."
                    if "allow_skill_installation" in missing:
                        return "Skill installation is disabled. Enable ‘Allow installing reviewed bundled skills by voice command’ first; I did not install anything."
                    if "allow_local_music" in missing:
                        return "Local music playback is disabled. Enable it in Settings and choose a folder first; no files were played."
                    return f"The {name.replace('_', ' ')} addon needs permission(s) that are currently disabled: {', '.join(missing)}. Review Security & permissions."
                answer = skill.handler(text, shared)
                if answer is not None:
                    return answer
        return None

    def descriptions(self) -> str:
        active = [skill for skill in self.skills.values() if skill.name in self.enabled]
        if not active:
            return "No skills are currently enabled. Open Skills in the desktop app to enable one."
        return "Enabled skills: " + "; ".join(f"{skill.name}: {skill.description}" for skill in active)
