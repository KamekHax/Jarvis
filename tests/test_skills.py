import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jarvis
from skill_manager import SkillManager
from skills.calculator_skill import calculate


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.skills_dir = Path(__file__).resolve().parents[1] / "skills"
        self.manager = SkillManager(
            self.skills_dir,
            enabled=["time", "calculator", "memory", "skills_help"],
        )

    def test_builtin_addons_load(self):
        names = {skill["name"] for skill in self.manager.list_skills()}
        self.assertEqual(names, {"time", "calculator", "memory", "skills_help", "learning",
                                 "coding", "theme_voice", "app_control", "conversion", "timer",
                                 "internet_search", "catalog"})
        self.assertFalse(self.manager.load_errors)

    def test_calculator_arithmetic(self):
        self.assertEqual(calculate("(9 + 3) / 4"), 3)
        response = self.manager.handle("calculate 45 * 12")
        self.assertEqual(response, "That equals 540.")

    def test_calculator_rejects_code(self):
        with self.assertRaises(ValueError):
            calculate("__import__('os').system('whoami')")

    def test_skill_enablement_changes_routing_and_help(self):
        assistant = jarvis.JarvisAssistant(jarvis.DEFAULTS.copy(), speech=jarvis.SpeechOutput(False))
        self.assertIn("calculator", assistant.execute("help"))
        assistant.skills.set_enabled("calculator", False)
        response = assistant.execute("calculate 1 + 1")
        self.assertIn("local chat model", response)

    def test_time_skill(self):
        answer = self.manager.handle("what time is it")
        self.assertTrue(answer.startswith("It is "))

    def test_plugin_added_after_start_is_discovered_by_rescan(self):
        with tempfile.TemporaryDirectory() as folder:
            plugins = Path(folder) / "skills"
            manager = SkillManager(plugins)
            self.assertEqual(manager.list_skills(), [])
            (plugins / "demo_skill.py").write_text(
                "def respond(text, context):\n"
                "    return 'discovered' if text == 'demo' else None\n"
                "def register(manager):\n"
                "    manager.register('demo', 'Demo plugin', respond)\n",
                encoding="utf-8",
            )
            manager.reload()
            manager.set_enabled("demo", True)
            self.assertEqual(manager.handle("demo"), "discovered")


if __name__ == "__main__":
    unittest.main()
