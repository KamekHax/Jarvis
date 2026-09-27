from __future__ import annotations

import hashlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import voicepacks


class FakeResponse(io.BytesIO):
    def geturl(self):
        return "https://cas-bridge.xethub.hf.co/model"


class VoicePackTests(unittest.TestCase):
    def test_voice_choices_are_unique_and_have_expected_languages(self):
        ids = [item[0] for item in voicepacks.VOICE_CHOICES.values()]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 11)
        self.assertEqual(voicepacks.VOICE_LANGUAGES["bm_george"], "en-gb")
        self.assertEqual(voicepacks.VOICE_LANGUAGES["af_michael"], "en-us")

    def test_model_assets_are_pinned_to_https_upstream_with_sha256(self):
        self.assertTrue(voicepacks.MODEL_REVISION)
        for asset in voicepacks.VOICE_PACK_FILES.values():
            self.assertTrue(asset["url"].startswith("https://huggingface.co/"))
            self.assertRegex(asset["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(asset["size"], 0)

    def test_download_accepts_trusted_cdn_and_checks_digest(self):
        content = b"verified local voice asset"
        metadata = {
            "filename": "test.bin", "url": "https://huggingface.co/pinned/test",
            "size": len(content), "sha256": hashlib.sha256(content).hexdigest(),
        }
        with tempfile.TemporaryDirectory() as folder, patch.dict(voicepacks.VOICE_PACK_FILES, {"test": metadata}), \
             patch("voicepacks.urlopen", return_value=FakeResponse(content)):
            path = voicepacks._download_asset("test", Path(folder))
            self.assertEqual(path.read_bytes(), content)
            self.assertFalse(path.with_suffix(".bin.part").exists())

    def test_download_discards_incomplete_or_invalid_content(self):
        metadata = {
            "filename": "test.bin", "url": "https://huggingface.co/pinned/test",
            "size": 100, "sha256": "0" * 64,
        }
        with tempfile.TemporaryDirectory() as folder, patch.dict(voicepacks.VOICE_PACK_FILES, {"test": metadata}), \
             patch("voicepacks.urlopen", return_value=FakeResponse(b"wrong-size")):
            with self.assertRaisesRegex(RuntimeError, "Incomplete voice download"):
                voicepacks._download_asset("test", Path(folder))
            self.assertFalse((Path(folder) / "test.bin.part").exists())
            self.assertFalse((Path(folder) / "test.bin").exists())

    def test_download_rejects_redirect_outside_trusted_host(self):
        content = b"asset"
        metadata = {
            "filename": "test.bin", "url": "https://huggingface.co/pinned/test",
            "size": len(content), "sha256": hashlib.sha256(content).hexdigest(),
        }
        response = FakeResponse(content)
        response.geturl = lambda: "https://attacker.example/test"
        with tempfile.TemporaryDirectory() as folder, patch.dict(voicepacks.VOICE_PACK_FILES, {"test": metadata}), \
             patch("voicepacks.urlopen", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "trusted HTTPS host"):
                voicepacks._download_asset("test", Path(folder))
            self.assertFalse((Path(folder) / "test.bin.part").exists())


if __name__ == "__main__":
    unittest.main()
