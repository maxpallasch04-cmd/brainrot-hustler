"""Offline tests for the YT-clip state machine + render (no network).

Run: python3 tests/test_yt_clips.py
"""

import json
import os
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
from moviepy import ColorClip, ImageSequenceClip, VideoFileClip  # noqa: E402
from PIL import Image  # noqa: E402

from yt_clips import crops  # noqa: E402
from yt_clips import download as dlmod  # noqa: E402
from yt_clips import highlights as hl  # noqa: E402
from yt_clips import ocr  # noqa: E402
from yt_clips.cli import (_candidate_windows, _layout_warnings,  # noqa: E402
                          _select_regions, main as yt_main)
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


class LayoutWarningTest(unittest.TestCase):
    def test_full_cover_has_no_warnings(self):
        regions = [
            {"name": "scoreboard", "box": [0, 0, 100, 20],
             "size": [180, 40], "fit": "cover", "position": [0, 0]},
            {"name": "action", "box": [0, 20, 100, 80],
             "size": [180, 280], "fit": "cover", "position": [0, 40]},
        ]
        self.assertEqual(_layout_warnings(regions, "180x320"), [])

    def test_gap_warns_about_black_bars(self):
        regions = [
            {"name": "scoreboard", "box": [0, 0, 100, 20],
             "size": [180, 40], "position": [0, 0]},
            {"name": "action", "box": [0, 20, 100, 80],
             "size": [180, 200], "fit": "cover", "position": [0, 40]},
        ]
        warnings = _layout_warnings(regions, "180x320")
        self.assertTrue(any("uncovered" in w and "black bars" in w for w in warnings))

    def test_contain_and_overflow_warn(self):
        regions = [
            {"name": "action", "box": [0, 0, 100, 100],
             "size": [180, 200], "fit": "contain", "position": [10, 10]},
        ]
        warnings = _layout_warnings(regions, "180x320")
        self.assertTrue(any("fit=contain" in w for w in warnings))
        self.assertTrue(any("uncovered" in w for w in warnings))

    def test_missing_size_and_position_warn(self):
        warnings = _layout_warnings([{"name": "action", "box": [0, 0, 10, 10]}],
                                    "180x320")
        self.assertTrue(any("no 'size'" in w for w in warnings))


    def test_whole_scoreboard_warns_when_score_box_exists(self):
        regions = [
            {"name": "scoreboard", "box": [0, 0, 300, 100], "size": [1080, 300],
             "fit": "cover", "position": [0, 0]},
            {"name": "action", "box": [0, 0, 100, 100], "size": [1080, 1620],
             "fit": "cover", "position": [0, 300]},
        ]
        warnings = _layout_warnings(regions, "1080x1920", {"score": [10, 10, 50, 50]})
        self.assertTrue(any("whole board" in w for w in warnings))
        self.assertTrue(any("not shown" in w for w in warnings))

    def test_score_region_needs_source_box(self):
        regions = [
            {"name": "score", "box": [0, 0, 100, 100], "size": [1080, 300],
             "fit": "cover", "position": [0, 0]},
            {"name": "action", "box": [0, 0, 100, 100], "size": [1080, 1620],
             "fit": "cover", "position": [0, 300]},
        ]
        warnings = _layout_warnings(regions, "1080x1920")
        self.assertTrue(any("no source box" in w for w in warnings))

    def test_score_too_small_warns(self):
        regions = [
            {"name": "score", "box": [0, 0, 100, 100], "size": [1080, 60],
             "fit": "cover", "position": [0, 0]},
            {"name": "action", "box": [0, 0, 100, 100], "size": [1080, 1860],
             "fit": "cover", "position": [0, 60]},
        ]
        warnings = _layout_warnings(regions, "1080x1920", {"score": [0, 0, 100, 100]})
        self.assertTrue(any("too small" in w for w in warnings))

    def test_score_aspect_mismatch_warns(self):
        regions = [
            {"name": "score", "box": [0, 0, 100, 100], "size": [1080, 300],
             "fit": "cover", "position": [0, 0]},
            {"name": "action", "box": [0, 0, 100, 100], "size": [1080, 1620],
             "fit": "cover", "position": [0, 300]},
        ]
        warnings = _layout_warnings(regions, "1080x1920", {"score": [0, 0, 100, 100]})
        self.assertTrue(any("target aspect" in w for w in warnings))


class CandidateWindowTest(unittest.TestCase):
    def test_score_anchor_builds_window(self):
        items, warnings = _candidate_windows(
            [{"score": 326, "pre_roll": 20, "post_roll": 3}])
        self.assertEqual(items[0]["start"], 306.0)
        self.assertEqual(items[0]["end"], 329.0)
        self.assertIn("Score @", items[0]["reason"])
        self.assertEqual(warnings, [])

    def test_short_pre_roll_warns(self):
        _, warnings = _candidate_windows([{"score": 360, "pre_roll": 5}])
        self.assertTrue(any("celebration" in w for w in warnings))

    def test_short_window_warns(self):
        _, warnings = _candidate_windows([{"start": 10, "end": 13}])
        self.assertTrue(any("too short" in w for w in warnings))

    def test_plain_candidate_untouched(self):
        items, warnings = _candidate_windows([{"start": 10, "end": 30, "reason": "x"}])
        self.assertEqual(items[0], {"start": 10.0, "end": 30.0, "reason": "x"})
        self.assertEqual(warnings, [])

    def test_segments_build_composite(self):
        items, warnings = _candidate_windows(
            [{"segments": [{"start": 10, "end": 12}, {"start": 30, "end": 33}]}])
        self.assertEqual(items[0]["start"], 10.0)
        self.assertEqual(items[0]["end"], 33.0)
        self.assertEqual(len(items[0]["segments"]), 2)
        self.assertEqual(warnings, [])

    def test_overlapping_segments_warn(self):
        _, warnings = _candidate_windows(
            [{"segments": [{"start": 10, "end": 15}, {"start": 14, "end": 20}]}])
        self.assertTrue(any("overlap" in w for w in warnings))


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


class SegmentRenderTest(unittest.TestCase):
    def test_segments_span_and_store(self):
        store = Store(Path(tempfile.mkdtemp()) / "t.db")
        try:
            sid = store.add_source("u", ext_id="seg", path="x.mp4")
            cid = store.add_candidates(sid, [{
                "segments": [{"start": 10, "end": 12}, {"start": 30, "end": 33}],
                "reason": "Trick + Score"}])[0]
            clip = store.get_clip(cid)
            self.assertEqual(clip["start_s"], 10.0)
            self.assertEqual(clip["end_s"], 33.0)
            segs = json.loads(clip["segments_json"])
            self.assertEqual([s["start"] for s in segs], [10.0, 30.0])
        finally:
            store.close()

    def test_two_segments_render_as_one_clip(self):
        tmp = Path(tempfile.mkdtemp())
        src = tmp / "src.mp4"
        clip = ColorClip(size=(160, 90), color=(10, 10, 10), duration=2.0)
        clip.write_videofile(str(src), fps=10, codec="libx264", audio=False, logger=None)
        clip.close()
        db = tmp / "t.db"
        store = Store(db)
        sid = store.add_source("u", ext_id="seg2", path=str(src))
        store.set_format(sid, {
            "size": "180x320", "background": "#101010",
            "regions": [
                {"name": "score", "box": [0, 0, 160, 20], "size": [180, 40],
                 "fit": "cover", "position": [0, 0]},
                {"name": "action", "box": [0, 20, 160, 70], "size": [180, 280],
                 "fit": "cover", "position": [0, 40]},
            ]})
        cid = store.add_candidates(sid, [{
            "segments": [{"start": 0.0, "end": 0.5}, {"start": 1.0, "end": 1.5}]}])[0]
        store.close()
        out = tmp / "out.mp4"
        yt_main(["--db", str(db), "clip", "--clip", str(cid), "--out", str(out)])
        self.assertTrue(out.exists())
        with VideoFileClip(str(out)) as check:
            self.assertAlmostEqual(check.duration, 1.0, delta=0.25)
            self.assertEqual(check.size, [180, 320])


class ScoreOcrTest(unittest.TestCase):
    def test_parse_value_range(self):
        self.assertEqual(ocr.parse_value("9.5"), (9.5, "9.5"))
        self.assertEqual(ocr.parse_value("9,50"), (9.5, "9,50"))
        self.assertEqual(ocr.parse_value("10.0"), (10.0, "10.0"))
        self.assertEqual(ocr.parse_value("O.5"), (0.5, "0.5"))
        self.assertIsNone(ocr.parse_value("12.0"))
        self.assertIsNone(ocr.parse_value("SCORE"))

    def test_runs_merge_same_value(self):
        got = ocr.runs([{"t": 326, "value": 9.5}, {"t": 327, "value": 9.5},
                        {"t": 330, "value": 9.5}], step=1.0)
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0]["count"], 2)
        self.assertEqual(got[1]["count"], 1)

    def _score_frame(self, text="9.5"):
        from PIL import ImageDraw, ImageFont
        font_path = Path(r"C:\Windows\Fonts\arialbd.ttf")
        if not font_path.is_file():
            self.skipTest("Arial Bold not available")
        img = Image.new("RGB", (360, 120), (20, 80, 20))
        draw = ImageDraw.Draw(img)
        draw.text((20, 5), text, font=ImageFont.truetype(str(font_path), 86),
                  fill=(255, 255, 255))
        return np.array(img)

    @unittest.skipUnless(ocr.tesseract_path(), "tesseract not installed")
    def test_read_frame(self):
        got = ocr.read_frame(self._score_frame(), (0, 0, 360, 120))
        self.assertIsNotNone(got)
        self.assertEqual(got["value"], 9.5)

    @unittest.skipUnless(ocr.tesseract_path(), "tesseract not installed")
    def test_scan_finds_score_in_video(self):
        tmp = Path(tempfile.mkdtemp())
        score = self._score_frame()
        blank = np.zeros((180, 320, 3), dtype=np.uint8)
        with_score = blank.copy()
        with_score[:107] = np.array(Image.fromarray(score).resize((320, 107)))
        video = tmp / "score.mp4"
        clip = ImageSequenceClip([blank, with_score], fps=1)
        clip.write_videofile(str(video), fps=1, codec="libx264", audio=False,
                             logger=None)
        clip.close()
        got = ocr.scan(video, (0, 0, 320, 107), [0.0, 1.0], step=1.0)
        self.assertEqual(got["checked"], 2)
        self.assertIsNotNone(got["first"])
        self.assertEqual(got["first"]["value"], 9.5)


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

    def setUp(self):
        # Isolate from a real node install; individual tests override this.
        patcher = mock.patch.object(dlmod.shutil, "which", return_value=None)
        self.addCleanup(patcher.stop)
        patcher.start()

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

    def test_js_runtime_auto_detects_node(self):
        with mock.patch.object(dlmod.shutil, "which", return_value="/usr/bin/node"):
            self._clear()
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
