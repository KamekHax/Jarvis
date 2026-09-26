import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from memory import MemoryStore
from permissions import add_approved_app
from skill_manager import SkillManager
from theme_manager import load_themes, save_theme
from themes import THEMES

ROOT = Path(__file__).resolve().parents[1]


class LocalCapabilitiesTests(unittest.TestCase):
    def skills(self, names):
        return SkillManager(ROOT / "skills", enabled=names)

    def test_taught_notes_and_selected_documents_persist_and_retrieve(self):
        with tempfile.TemporaryDirectory() as folder:
            store = MemoryStore(Path(folder) / "memory.sqlite3")
            store.save_knowledge("Open source preference", "I prefer open-source software and Python.")
            store.save_knowledge_document("design.md", "The local project uses a custom Arc Reactor palette.")
            reopened = MemoryStore(Path(folder) / "memory.sqlite3")
            self.assertIn("open-source", reopened.relevant_context("What software do I prefer?"))
            self.assertIn("Arc Reactor", reopened.relevant_context("What palette does my design use?"))
            self.assertEqual(len(reopened.learned_knowledge()), 2)

    def test_learning_voice_skill_saves_a_fact_and_file_read_is_opt_in(self):
        with tempfile.TemporaryDirectory() as folder:
            store = MemoryStore(Path(folder) / "memory.sqlite3")
            skills = self.skills(["learning"])
            context = {"memory": store, "skills": skills, "permissions": {}, "actions": {}}
            saved = skills.handle("Learn that my app uses Rust", context)
            self.assertIn("saved", saved.lower())
            self.assertIn("Rust", store.learned_knowledge()[0]["content"])
            blocked = skills.handle("Learn from a file", context)
            self.assertIn("disabled", blocked.lower())

    def test_app_control_requires_permission_and_named_approved_path(self):
        skills = self.skills(["app_control"])
        blocked = skills.handle("Open app Notepad", {"permissions": {}})
        self.assertIn("permission", blocked.lower())
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "test-app"
            target.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            target.chmod(0o755)
            settings = {"allow_app_launching": True, "approved_apps": {}}
            add_approved_app(settings, "Test editor", target)
            with patch("permissions.platform.system", return_value="Linux"), patch("permissions.subprocess.Popen") as launch:
                answer = skills.handle("Launch app test editor", {"permissions": settings})
            self.assertIn("Opened approved", answer)
            launch.assert_called_once_with([str(target.resolve())], close_fds=True)
            denied = skills.handle("Open app shell", {"permissions": settings})
            self.assertIn("not on", denied)

    def test_app_approval_rejects_script_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "do-not-launch.py"
            source.write_text("print('hi')\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Script"):
                add_approved_app({}, "script", source)

    def test_coding_skill_saves_only_into_selected_workspace_without_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = {"allow_workspace_writes": True, "workspace_dir": folder}
            assistant = type("Assistant", (), {"last_response": "Here is the function:\n```python\nprint('hello')\n```"})()
            skills = self.skills(["coding"])
            context = {"skills": skills, "permissions": settings, "assistant": assistant}
            answer = skills.handle("Save the last code as Hello World.py", context)
            self.assertIn("Saved", answer)
            output = Path(folder) / "Hello World.py"
            self.assertEqual(output.read_text(encoding="utf-8").strip(), "print('hello')")
            self.assertIn("never overwrites", skills.handle("Save the last code as Hello World.py", context))

    def test_coding_permission_blocks_before_handler(self):
        skills = self.skills(["coding"])
        answer = skills.handle("Save code as x.py", {"permissions": {}, "assistant": None})
        self.assertIn("disabled", answer.lower())

    def test_local_theme_addons_are_json_and_validated(self):
        with tempfile.TemporaryDirectory() as folder:
            saved = save_theme("Local Test", next(iter(THEMES.values())), Path(folder))
            self.assertTrue(saved.is_file())
            self.assertIn("Local Test", load_themes(Path(folder)))
            with self.assertRaises(ValueError):
                save_theme("Broken", {"background": "not-a-color"}, Path(folder))

    def test_offline_conversion_and_timer_plugins(self):
        skills = self.skills(["conversion", "timer"])
        converted = skills.handle("Convert 12 miles to km")
        self.assertIn("19.31 km", converted)
        scheduled = []
        answer = skills.handle("Set a timer for 5 minutes", {"actions": {"set_timer": lambda seconds, label: scheduled.append((seconds, label)) or "Timer set."}})
        self.assertEqual(answer, "Timer set.")
        self.assertEqual(scheduled, [(300, "5 minutes")])
        self.assertEqual(skills.handle("cancel all timers", {"actions": {"cancel_timers": lambda: "Cancelled."}}), "Cancelled.")

    def test_integration_modules_are_not_imported_until_permissions_are_enabled(self):
        with tempfile.TemporaryDirectory() as folder:
            plugins = Path(folder) / "user_skills"
            plugins.mkdir()
            marker = Path(folder) / "imported.txt"
            module = plugins / "demo_integration.py"
            module.write_text(
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('imported')\n"
                "def matches(text): return text.lower().startswith('integration ping')\n"
                "def handle(text, context): return 'integration handled'\n"
                "def register(manager): manager.register('demo_integration', 'demo', handle, permissions=('allow_workspace_writes',), matcher=matches)\n",
                encoding="utf-8",
            )
            _disabled = SkillManager(plugins, enabled=["demo_integration"], allow_integrations=False)
            self.assertFalse(marker.exists())
            enabled = SkillManager(plugins, enabled=["demo_integration"], allow_integrations=True)
            self.assertTrue(marker.exists())
            self.assertIn("allow_external_integrations", enabled.skills["demo_integration"].permissions)
            blocked = enabled.handle("integration ping", {"permissions": {"allow_external_integrations": True}})
            self.assertIn("allow_workspace_writes", blocked)
            answer = enabled.handle("integration ping", {"permissions": {
                "allow_external_integrations": True, "allow_workspace_writes": True,
            }})
            self.assertEqual(answer, "integration handled")


if __name__ == "__main__":
    unittest.main()
