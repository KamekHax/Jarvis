import sys
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import installer


class InstallerTests(unittest.TestCase):
    def test_active_python_is_discovered_without_recursive_scan(self):
        expected = Path(sys.executable).resolve()
        with patch.object(installer, "_quick_candidates", return_value=[expected]), \
             patch.object(installer, "_deep_candidates", side_effect=AssertionError("unexpected deep scan")):
            found, diagnostics = installer.discover_python()
        self.assertEqual(found, expected)
        self.assertEqual(diagnostics, [])

    def test_fallback_search_finds_python_outside_path(self):
        hidden = Path("/unusual/apps/python/bin/python3")
        with patch.object(installer, "_quick_candidates", return_value=[]), \
             patch.object(installer, "_deep_candidates", return_value=[hidden]), \
             patch.object(installer, "_version_at", return_value=(3, 12, 3)):
            found, _diagnostics = installer.discover_python(search_seconds=1)
        self.assertEqual(found, hidden.resolve())

    def test_old_python_is_rejected(self):
        with patch.object(installer, "_quick_candidates", return_value=[Path("/old/python")]), \
             patch.object(installer, "_deep_candidates", return_value=[]), \
             patch.object(installer, "_version_at", return_value=(3, 9, 20)):
            found, diagnostics = installer.discover_python(search_seconds=1)
        self.assertIsNone(found)
        self.assertTrue(any("too old" in message for message in diagnostics))

    def test_virtual_environment_interpreter_path(self):
        env = Path("/project/.venv")
        if sys.platform == "win32":
            self.assertEqual(installer.venv_python(env), env / "Scripts" / "python.exe")
        else:
            self.assertEqual(installer.venv_python(env), env / "bin" / "python")

    def test_current_python_meets_minimum(self):
        version = installer._version_at(Path(sys.executable))
        self.assertIsNotNone(version)
        self.assertGreaterEqual(version[:2], (3, 10))

    def test_local_chat_model_is_default_with_explicit_opt_out(self):
        self.assertTrue(installer.build_parser().parse_args([]).with_chat)
        self.assertFalse(installer.build_parser().parse_args(["--without-chat"]).with_chat)

    def test_setup_forwards_model_choice_to_bootstrap(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            python = root / "python"
            python.write_text("test runtime")
            with patch.object(installer, "ROOT", root), \
                 patch.object(installer, "venv_python", return_value=python), \
                 patch.object(installer, "_version_at", return_value=(3, 12, 1)), \
                 patch.object(installer.subprocess, "run") as run:
                run.return_value = subprocess.CompletedProcess([], 0)
                self.assertEqual(installer.install(), 0)
                setup_args = run.call_args.args[0]
                self.assertIn("--with-chat", setup_args)
                run.reset_mock()
                self.assertEqual(installer.install(with_chat=False), 0)
                self.assertIn("--without-chat", run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
