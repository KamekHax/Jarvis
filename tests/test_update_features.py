from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import jarvis
from music_player import LocalMusicPlayer
from skill_catalog import CATALOG, install_skill, trusted_hashes
from skill_manager import SkillManager


class UpdateFeatureTests(unittest.TestCase):
    def test_explicit_search_skill_is_permission_gated(self):
        manager = SkillManager(ROOT / "skills", enabled=["internet_search"])
        calls = []
        context = {"permissions": {"allow_internet_search": False},
                   "actions": {"search_web": lambda query: calls.append(query) or "searched"}}
        response = manager.handle("Google current weather in Oslo", context)
        self.assertIn("did not send", response)
        self.assertEqual(calls, [])
        context["permissions"]["allow_internet_search"] = True
        response = manager.handle("Google current weather in Oslo", context)
        self.assertEqual(response, "searched")
        self.assertEqual(calls, ["current weather in Oslo"])

    def test_inferred_web_fallback_does_not_send_an_online_query(self):
        class Chat:
            def ask(self, _prompt):
                return "JARVIS_WEB_SEARCH_REQUIRED: generic topic"

        assistant = jarvis.JarvisAssistant(jarvis.DEFAULTS.copy(), speech=jarvis.SpeechOutput(False), chat=Chat())
        assistant.desktop_settings = {"allow_internet_search": True}
        with patch.object(assistant, "_search_web") as search:
            answer = assistant.handle_text("What is happening today?", require_wake=False)
        search.assert_not_called()
        self.assertIn("I did not send anything online", answer)

    def test_private_topics_never_reach_search(self):
        assistant = jarvis.JarvisAssistant(jarvis.DEFAULTS.copy(), speech=jarvis.SpeechOutput(False))
        self.assertTrue(assistant._private_web_query("my home address"))
        self.assertTrue(assistant._private_web_query("account password"))
        self.assertFalse(assistant._private_web_query("official Python 3.14 release"))
        with patch("internet_search.open_search_in_default_browser") as browser, \
             patch("internet_search.search_results") as fetch:
            answer = assistant._search_web("my home address")
        browser.assert_not_called()
        fetch.assert_not_called()
        self.assertIn("kept that search local", answer)

    def test_explicit_search_sends_only_query_and_returns_citations(self):
        assistant = jarvis.JarvisAssistant(jarvis.DEFAULTS.copy(), speech=jarvis.SpeechOutput(False))
        assistant.desktop_settings = {"browser_search_engine": "DuckDuckGo"}
        sample = [{"title": "Python docs", "url": "https://docs.python.org/", "snippet": "Official docs."}]
        with patch("internet_search.open_search_in_default_browser", return_value=True) as browser, \
             patch("internet_search.search_results", return_value=sample) as search:
            answer = assistant._search_web("official Python docs")
        browser.assert_called_once_with("official Python docs", "DuckDuckGo")
        search.assert_called_once_with("official Python docs")
        self.assertIn("https://docs.python.org/", answer)
        self.assertIn("Opened DuckDuckGo", answer)

    def test_catalog_requires_permission_and_runs_installer_only_on_explicit_command(self):
        manager = SkillManager(ROOT / "skills", enabled=["catalog"])
        calls = []
        context = {"permissions": {"allow_skill_installation": False},
                   "actions": {"install_skill": lambda name: calls.append(name) or "installed"},
                   "catalog": {"music": "local audio"}}
        blocked = manager.handle("Install skill music", context)
        self.assertIn("did not install", blocked)
        self.assertEqual(calls, [])
        context["permissions"]["allow_skill_installation"] = True
        self.assertEqual(manager.handle("Install skill music", context), "installed")
        self.assertEqual(calls, ["music"])

    def test_optional_music_skill_is_not_auto_discovered(self):
        builtins = SkillManager(ROOT / "skills", enabled=["music"])
        self.assertNotIn("music", builtins.skills)
        addon = ROOT / "bundled_addons" / CATALOG["music"]["filename"]
        self.assertTrue(addon.is_file())
        self.assertEqual(hashlib.sha256(addon.read_bytes()).hexdigest(), trusted_hashes()[addon.name])

    def test_music_player_reads_only_direct_audio_children(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary) / "music"
            nested = base / "nested"
            outside = Path(temporary) / "outside.mp3"
            nested.mkdir(parents=True)
            base.joinpath("one.mp3").write_bytes(b"audio")
            base.joinpath("notes.txt").write_text("not audio")
            nested.joinpath("two.flac").write_bytes(b"audio")
            outside.write_bytes(b"external")
            try:
                base.joinpath("alias.mp3").symlink_to(outside)
            except OSError:
                pass
            player = LocalMusicPlayer(base)
            player._load_library()
            self.assertEqual([path.name for path in player._playlist], ["one.mp3"])

    def test_music_commands_require_local_playback_permission(self):
        manager = SkillManager(ROOT / "bundled_addons", enabled=["music"], trusted_hashes=trusted_hashes())
        blocked = manager.handle("Play music", {"permissions": {"allow_local_music": False}})
        self.assertIn("disabled", blocked)

    def test_catalog_installer_rejects_unknown_or_unpinned_addons(self):
        message, path = install_skill("unknown music source", destination=ROOT / ".tmp-test-addon")
        self.assertIsNone(path)
        self.assertIn("not in the bundled addon catalog", message)
        original = CATALOG["music"]["sha256"]
        try:
            CATALOG["music"]["sha256"] = "invalid"
            message, path = install_skill("music", destination=ROOT / ".tmp-test-addon")
            self.assertIsNone(path)
            self.assertIn("no valid integrity pin", message)
        finally:
            CATALOG["music"]["sha256"] = original


if __name__ == "__main__":
    unittest.main()
