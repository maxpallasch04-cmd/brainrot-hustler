"""Offline tests for the YT-clip state machine + render (no network).

Run: python3 tests/test_yt_clips.py
"""

import os
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
from moviepy import ColorClip, VideoFileClip  # noqa: E402
from PIL import Image  # noqa: E402

from yt_clips import crops  # noqa: E402
from yt_clips import download as dlmod  # noqa: E402
from yt_clips import highlights as hl  # noqa: E402
from yt_clips.cli import _select_regions, main as yt_main  # noqa: E402
from yt_clips.store import Store  # noqa: E402

FORMAT = {
    "size": "180x320",
    "background": "#101010",
    "regions": [
        {"box": [0, 0, 160, 20], "size": [180, 40], "position": [0, 0]},
        {"box": [0, 20, 160, 70], "size": [180, 280], "position": [0, 40]},
    ],
}


class YoutubeIdTest(unittest.TestCase):
    def test_ids(self):
        self.assertEqual(dlmod.youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
                         "dQw4w9WgXcQ")
        self.assertEqual(dlmod.youtube_id("https://youtu.be/dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(dlmod.youtube_id("https://www.youtube.com/shorts/abcDEF12345"),
                         "abcDEF12345")
        self.assertIsNone(dlmod.youtube_id("https://example.com/x"))


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.store = Store(self.tmp / "t.db")

    def tearDown(self):
        self.store.close()

    def test_empty_queue_is_download(self):
        self.assertEqual(self.store.next_work()["action"], "download")

    def test_format_step_first(self):
        sid = self.store.add_source("https://youtu.be/abc", ext_id="abc", path="x.mp4")
        nw = self.store.next_work()
        self.assertEqual(nw["action"], "format")
        self.assertEqual(nw["source"]["id"], sid)

    def test_format_then_find_then_clip(self):
        sid = self.store.add_source("u", ext_id="v1", path="x.mp4")
        self.store.set_format(sid, FORMAT)
        self.assertEqual(self.store.get_source(sid)["status"], "Formatted")
        self.assertEqual(self.store.next_work()["action"], "find")
        ids = self.store.add_candidates(sid, [{"start": 1.0, "end": 5.0, "reason": "Tor"}])
        nw = self.store.next_work()
        self.assertEqual(nw["action"], "clip")
        self.assertEqual(nw["clip"]["id"], ids[0])
        self.store.mark_clip(ids[0], "Used")
        self.assertEqual(self.store.get_source(sid)["status"], "Exhausted")
        self.assertEqual(self.store.next_work()["action"], "download")

    def test_upsert_by_ext_id(self):
        a = self.store.add_source("u1", ext_id="same", path="a.mp4")
        b = self.store.add_source("u2", ext_id="same", path="b.mp4")
        self.assertEqual(a, b)
        self.assertEqual(self.store.get_source(a)["path"], "b.mp4")

    def test_bad_window_rejected(self):
        sid = self.store.add_source("u", ext_id="w", path="x.mp4")
        with self.assertRaises(ValueError):
            self.store.add_candidates(sid, [{"start": 5.0, "end": 5.0}])

    def test_list_sources_counts(self):
        sid = self.store.add_source("u", ext_id="c", path="x.mp4")
        self.store.set_format(sid, FORMAT)
        self.store.add_candidates(sid, [{"start": 0, "end": 1}, {"start": 2, "end": 3}])
        row = self.store.list_sources()[0]
        self.assertEqual(row["candidates"], 2)
        self.assertEqual(row["used"], 0)


class ClipRenderTest(unittest.TestCase):
    def test_clip_uses_stored_format(self):
        tmp = Path(tempfile.mkdtemp())
        src = tmp / "src.mp4"
        clip = ColorClip(size=(160, 90), color=(10, 10, 10), duration=1.0)
        clip.write_videofile(str(src), fps=10, codec="libx264", audio=False, logger=None)
        clip.close()

        db = tmp / "t.db"
        store = Store(db)
        sid = store.add_source("u", ext_id="r1", path=str(src))
        store.set_format(sid, FORMAT)
        ids = store.add_candidates(sid, [{"start": 0.0, "end": 0.9, "reason": "test"}])
        store.close()

        out = tmp / "out.mp4"
        yt_main(["--db", str(db), "clip", "--clip", str(ids[0]), "--out", str(out), "--used"])
        self.assertTrue(out.exists())
        with VideoFileClip(str(out)) as check:
            self.assertEqual(check.size, [180, 320])

        store = Store(db)
        try:
            self.assertEqual(store.get_clip(ids[0])["status"], "Used")
            self.assertEqual(store.get_source(sid)["status"], "Exhausted")
        finally:
            store.close()


class HighlightsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _write_audio(self, path, duration=10.0, rate=22050, burst=(6.0, 8.0)):
        """Deterministic mono WAV via the stdlib (exact rate + duration)."""
        rng = np.random.default_rng(0)
        n = int(duration * rate)
        sig = rng.standard_normal(n) * 0.01
        lo, hi = int(burst[0] * rate), int(burst[1] * rate)
        sig[lo:hi] = rng.standard_normal(hi - lo) * 0.9
        pcm = (np.clip(sig, -1.0, 1.0) * 32767).astype("<i2")
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(pcm.tobytes())

    def test_audio_peak_found_near_burst(self):
        wav = self.tmp / "a.wav"
        self._write_audio(wav)
        peaks = hl.audio_peaks(str(wav), top=3, k=1.0)
        self.assertTrue(peaks)
        self.assertTrue(any(5.0 <= p["t"] <= 9.0 for p in peaks), peaks)

    def test_detect_keeps_chapters(self):
        wav = self.tmp / "b.wav"
        self._write_audio(wav)
        cands = hl.detect(str(wav),
                          chapters=[{"start_time": 1.0, "end_time": 3.0, "title": "Anpfiff"}],
                          top=3)
        self.assertTrue(any(c["signal"] == "chapter" for c in cands))
        self.assertTrue(any("Anpfiff" in c["reason"] for c in cands))
        self.assertEqual([c["start"] for c in cands],
                         sorted(c["start"] for c in cands))

    def test_chapters_roundtrip(self):
        store = Store(self.tmp / "t.db")
        try:
            sid = store.add_source("u", ext_id="ch", path="x.mp4",
                                   chapters=[{"start_time": 1.0, "title": "X"}])
            self.assertEqual(store.get_chapters(sid)[0]["title"], "X")
        finally:
            store.close()


class CropsTest(unittest.TestCase):
    def test_crop_frame_and_map_back(self):
        tmp = Path(tempfile.mkdtemp())
        src = tmp / "frame.png"
        Image.new("RGB", (400, 300), (20, 40, 60)).save(src)
        out = tmp / "sb.png"
        got = crops.crop_frame(str(src), (100, 50, 200, 100), str(out), scale=2.0)
        self.assertEqual(got["size"], [400, 200])
        self.assertEqual(got["offset"], [100, 50])
        self.assertTrue(out.exists())
        self.assertEqual(crops.map_back((20, 10, 40, 20), got["offset"], got["scale"]),
                         [110, 55, 20, 10])

    def test_crop_frame_clamps(self):
        tmp = Path(tempfile.mkdtemp())
        src = tmp / "f.png"
        Image.new("RGB", (100, 60), (0, 0, 0)).save(src)
        got = crops.crop_frame(str(src), (90, 50, 500, 500), str(tmp / "o.png"), scale=1.0)
        self.assertEqual(got["size"], [10, 10])


class SelectionTest(unittest.TestCase):
    def test_select_regions(self):
        regions = [{"name": "scoreboard", "box": [0, 0, 10, 10]},
                   {"name": "action", "box": [0, 10, 10, 10]},
                   {"box": [1, 1, 2, 2]}]  # unnamed is always kept
        self.assertEqual([r.get("name") for r in _select_regions(regions, drop="scoreboard")],
                         ["action", None])
        self.assertEqual([r.get("name") for r in _select_regions(regions, only="action")],
                         ["action", None])
        with self.assertRaises(ValueError):
            _select_regions(regions, only="nope")

    def test_clip_format_override(self):
        store = Store(Path(tempfile.mkdtemp()) / "t.db")
        try:
            sid = store.add_source("u", ext_id="f", path="x.mp4")
            store.set_format(sid, FORMAT)
            cid = store.add_candidates(sid, [{"start": 0, "end": 1}])[0]
            self.assertIsNone(store.get_clip_format(cid))
            store.set_clip_format(cid, {"regions": [{"name": "action", "box": [0, 0, 1, 1]}]})
            self.assertEqual(store.get_clip_format(cid)["regions"][0]["name"], "action")
        finally:
            store.close()

    def test_clip_drop_region_renders(self):
        tmp = Path(tempfile.mkdtemp())
        src = tmp / "src.mp4"
        clip = ColorClip(size=(160, 90), color=(10, 10, 10), duration=1.0)
        clip.write_videofile(str(src), fps=10, codec="libx264", audio=False, logger=None)
        clip.close()
        db = tmp / "t.db"
        store = Store(db)
        sid = store.add_source("u", ext_id="dr", path=str(src))
        store.set_format(sid, {
            "size": "180x320", "background": "#101010",
            "regions": [
                {"name": "scoreboard", "box": [0, 0, 160, 20], "size": [180, 40], "position": [0, 0]},
                {"name": "action", "box": [0, 20, 160, 70], "size": [180, 280], "position": [0, 0]},
            ]})
        cid = store.add_candidates(sid, [{"start": 0.0, "end": 0.9}])[0]
        store.close()
        out = tmp / "out.mp4"
        yt_main(["--db", str(db), "clip", "--clip", str(cid), "--out", str(out),
                 "--drop", "scoreboard"])
        self.assertTrue(out.exists())
        with VideoFileClip(str(out)) as check:
            self.assertEqual(check.size, [180, 320])


class CookieOptsTest(unittest.TestCase):
    """YouTube bot gate: cookies must reach yt-dlp (no network)."""

    def _clear(self):
        os.environ.pop("YTDLP_COOKIES_FILE", None)
        os.environ.pop("YTDLP_COOKIES_FROM_BROWSER", None)

    def test_file_env(self):
        env = {"YTDLP_COOKIES_FILE": "/tmp/c.txt", "YTDLP_COOKIES_FROM_BROWSER": ""}
        with mock.patch.dict(os.environ, env, clear=False):
            self.assertEqual(dlmod.cookie_opts(), {"cookiefile": str(Path("/tmp/c.txt"))})

    def test_from_browser_env(self):
        with mock.patch.dict(os.environ, {"YTDLP_COOKIES_FROM_BROWSER": "firefox:default"}, clear=False):
            os.environ.pop("YTDLP_COOKIES_FILE", None)
            self.assertEqual(dlmod.cookie_opts(), {"cookiesfrombrowser": ("firefox", "default")})

    def test_default_state_dir_file(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "cookies.txt").write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"BRAINROT_STATE_DIR": d}, clear=False):
                self._clear()
                self.assertEqual(dlmod.cookie_opts(), {"cookiefile": str(Path(d, "cookies.txt"))})

    def test_empty_when_unconfigured(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"BRAINROT_STATE_DIR": d}, clear=False):
                self._clear()
                self.assertEqual(dlmod.cookie_opts(), {})

    def test_bot_check_becomes_actionable(self):
        err = dlmod._with_hint(Exception("ERROR: Sign in to confirm you're not a bot. Use --cookies"))
        self.assertIsInstance(err, RuntimeError)
        self.assertIn("cookies", str(err).lower())

    def test_other_errors_pass_through(self):
        original = ValueError("nope")
        self.assertIs(dlmod._with_hint(original), original)

    def test_ytdlp_accepts_the_opts(self):
        try:
            import yt_dlp
        except ImportError:
            self.skipTest("yt-dlp not installed")
        with tempfile.TemporaryDirectory() as d:
            Path(d, "cookies.txt").write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"BRAINROT_STATE_DIR": d}, clear=False):
                self._clear()
                yt_dlp.YoutubeDL({"quiet": True, **dlmod.cookie_opts()}).close()


class NetOptsTest(unittest.TestCase):
    """IP-block escape hatches (proxy / player client), no network."""

    def _clear(self):
        os.environ.pop("YTDLP_PROXY", None)
        os.environ.pop("YTDLP_EXTRACTOR_ARGS", None)
        os.environ.pop("YTDLP_JS_RUNTIMES", None)

    def test_proxy_env(self):
        with mock.patch.dict(os.environ, {"YTDLP_PROXY": "socks5://h:1080"}, clear=False):
            os.environ.pop("YTDLP_EXTRACTOR_ARGS", None)
            self.assertEqual(dlmod.net_opts(), {"proxy": "socks5://h:1080"})

    def test_extractor_args_env(self):
        env = {"YTDLP_EXTRACTOR_ARGS": "youtube:player_client=tv,web_safari"}
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("YTDLP_PROXY", None)
            self.assertEqual(dlmod.net_opts(), {
                "extractor_args": {"youtube": {"player_client": ["tv", "web_safari"]}},
            })

    def test_extractor_args_escaping(self):
        env = {"YTDLP_EXTRACTOR_ARGS": "youtube:player-client=a\\,b"}
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("YTDLP_PROXY", None)
            self.assertEqual(dlmod.net_opts(), {
                "extractor_args": {"youtube": {"player_client": ["a,b"]}},
            })

    def test_empty_when_unconfigured(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            self._clear()
            self.assertEqual(dlmod.net_opts(), {})

    def test_bad_extractor_args_ignored(self):
        with mock.patch.dict(os.environ, {"YTDLP_EXTRACTOR_ARGS": "nonsense"}, clear=False):
            os.environ.pop("YTDLP_PROXY", None)
            self.assertEqual(dlmod.net_opts(), {})

    def test_js_runtimes_env(self):
        with mock.patch.dict(os.environ, {"YTDLP_JS_RUNTIMES": "node"}, clear=False):
            self.assertEqual(dlmod.net_opts(), {"js_runtimes": {"node": {"path": None}}})

    def test_js_runtimes_list_with_path(self):
        env = {"YTDLP_JS_RUNTIMES": "node:/usr/bin/node, deno"}
        with mock.patch.dict(os.environ, env, clear=False):
            self.assertEqual(dlmod.net_opts(), {
                "js_runtimes": {
                    "node": {"path": "/usr/bin/node"},
                    "deno": {"path": None},
                },
            })

    def test_ytdlp_accepts_net_opts(self):
        try:
            import yt_dlp
        except ImportError:
            self.skipTest("yt-dlp not installed")
        env = {"YTDLP_PROXY": "http://127.0.0.1:9",
               "YTDLP_EXTRACTOR_ARGS": "youtube:player_client=tv",
               "YTDLP_JS_RUNTIMES": "node"}
        with mock.patch.dict(os.environ, env, clear=False):
            yt_dlp.YoutubeDL({"quiet": True, **dlmod.net_opts()}).close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
