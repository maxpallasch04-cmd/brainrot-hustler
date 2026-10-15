"""Offline unit tests for the hosting download layer (no network).

Run: python3 tests/test_hosting.py
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import importlib  # noqa: E402

dl = importlib.import_module("hosting.download")  # noqa: E402
from hosting.download import DownloadError, download, filename_from  # noqa: E402


class _StreamResp:
    def __init__(self, content, status=200, url="https://host.example/abc.mp4",
                 headers=None, chunk=4):
        self._content = content
        self.status_code = status
        self.url = url
        self.headers = headers or {}
        self._chunk = chunk

    def iter_content(self, chunk_size=1024):
        step = min(chunk_size, self._chunk)
        for i in range(0, len(self._content), step):
            yield self._content[i:i + step]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class DownloadTest(unittest.TestCase):
    def test_filename_from_url(self):
        self.assertEqual(filename_from("https://x/y/clip.mp4"), "clip.mp4")

    def test_filename_from_disposition(self):
        self.assertEqual(
            filename_from("https://x/y", 'attachment; filename="real name.mp4"'),
            "real_name.mp4")

    def test_download_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "clip.mp4"
            resp = _StreamResp(b"hello world")
            with mock.patch.object(dl.requests, "get", return_value=resp):
                info = download("https://host.example/abc.mp4", dest=dest)
            self.assertEqual(dest.read_bytes(), b"hello world")
            self.assertEqual(info["bytes"], 11)
            self.assertEqual(info["filename"], "clip.mp4")
            self.assertEqual(info["url"], "https://host.example/abc.mp4")

    def test_download_infers_name_into_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            resp = _StreamResp(b"abc", url="https://x/foo/bar.mp4")
            with mock.patch.object(dl.requests, "get", return_value=resp):
                info = download("https://x/foo/bar.mp4", out_dir=tmp)
            self.assertEqual(Path(info["path"]).name, "bar.mp4")
            self.assertTrue((Path(tmp) / "bar.mp4").is_file())

    def test_download_http_error(self):
        resp = _StreamResp(b"", status=404)
        with mock.patch.object(dl.requests, "get", return_value=resp):
            with self.assertRaises(DownloadError):
                download("https://x/missing.mp4", dest="ignored")

    def test_download_bad_url(self):
        with self.assertRaises(DownloadError):
            download("ftp://x/y.mp4")

    def test_download_max_bytes_aborts_and_cleans(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "clip.mp4"
            resp = _StreamResp(b"0123456789")
            with mock.patch.object(dl.requests, "get", return_value=resp):
                with self.assertRaises(DownloadError):
                    download("https://x/big.mp4", dest=dest, max_bytes=5)
            self.assertFalse(dest.exists())
            self.assertFalse((Path(tmp) / "clip.mp4.part").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
