import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import download_local_model


class FakeResponse:
    def __init__(self, data: bytes, status: int, headers: dict[str, str]):
        self.stream = io.BytesIO(data)
        self.status = status
        self.headers = headers

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def getcode(self):
        return self.status

    def read(self, size=-1):
        return self.stream.read(size)


class DownloadTests(unittest.TestCase):
    def test_complete_download_installs_atomically(self):
        with tempfile.TemporaryDirectory() as folder:
            fake = FakeResponse(b"GGUF-model", 200, {"Content-Length": "10"})
            with patch.object(download_local_model, "MODELS", Path(folder)), \
                 patch.object(download_local_model, "MIN_MODEL_BYTES", 5), \
                 patch.object(download_local_model.urllib.request, "urlopen", return_value=fake):
                self.assertEqual(download_local_model.main(), 0)
            target = Path(folder) / download_local_model.FILENAME
            self.assertEqual(target.read_bytes(), b"GGUF-model")
            self.assertFalse(target.with_suffix(target.suffix + ".part").exists())

    def test_partial_download_resumes_using_range(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            partial = root / (download_local_model.FILENAME + ".part")
            partial.write_bytes(b"ABC")
            response = FakeResponse(b"DEF", 206, {
                "Content-Length": "3", "Content-Range": "bytes 3-5/6"
            })
            captured = []

            def fake_open(request, timeout):
                captured.append(request.headers.get("Range"))
                return response

            with patch.object(download_local_model, "MODELS", root), \
                 patch.object(download_local_model, "MIN_MODEL_BYTES", 5), \
                 patch.object(download_local_model.urllib.request, "urlopen", side_effect=fake_open):
                self.assertEqual(download_local_model.main(), 0)
            self.assertEqual(captured, ["bytes=3-"])
            self.assertEqual((root / download_local_model.FILENAME).read_bytes(), b"ABCDEF")


if __name__ == "__main__":
    unittest.main()
