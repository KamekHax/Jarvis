import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop_settings import load_settings, save_settings, set_startup_enabled
from hotkeys import pynput_combo, tkinter_sequence


class DesktopSettingsTests(unittest.TestCase):
    def test_settings_round_trip_and_range_clamp(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            save_settings({"scale": 3.0, "opacity": 0.2, "animation_performance": "ultra"}, path)
            settings = load_settings(path)
            self.assertEqual(settings["scale"], 1.5)
            self.assertEqual(settings["opacity"], 0.45)
            self.assertEqual(settings["animation_performance"], "medium")

    def test_shortcut_format(self):
        self.assertEqual(pynput_combo("ctrl+alt+o"), "<ctrl>+<alt>+o")
        self.assertEqual(pynput_combo("alt+f10"), "<alt>+f10")
        self.assertEqual(tkinter_sequence("ctrl+alt+o"), "<Control-Alt-o>")
        with self.assertRaises(ValueError):
            tkinter_sequence("ctrl+alt+not a key")

    def test_windows_startup_file_is_reversible(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch("desktop_settings.platform.system", return_value="Windows"), \
                 patch.dict(os.environ, {"APPDATA": folder}):
                set_startup_enabled(True, root)
                startup = root / "Microsoft/Windows/Start Menu/Programs/Startup/JARVIS-Local.cmd"
                self.assertTrue(startup.is_file())
                self.assertIn("run.py", startup.read_text())
                set_startup_enabled(False, root)
                self.assertFalse(startup.exists())


if __name__ == "__main__":
    unittest.main()
