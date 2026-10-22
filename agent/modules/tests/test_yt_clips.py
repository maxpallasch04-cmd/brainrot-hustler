"""Offline tests for the YT-clip state machine + render (no network).

Run: python3 tests/test_yt_clips.py
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
from editor.probe import ffmpeg_exe  # noqa: E402
from PIL import Image  # noqa: E402

from yt_clips import crops  # noqa: E402
from yt_clips.urls import youtube_id  # noqa: E402
from yt_clips import highlights as hl  # noqa: E402
from yt_clips import motion  # noqa: E402
from yt_clips import ocr  # noqa: E402
from yt_clips.cli import _candidate_windows, main as yt_main  # noqa: E402
from yt_clips import cli as cli_mod  # noqa: E402
from yt_clips.cli import http_download  # noqa: E402
from yt_clips.store import Store  # noqa: E402
from longterm_memory import db as ltm  # noqa: E402


def write_video(path, frames, fps=10):
    """Bildfolge als MP4 - ffmpeg statt MoviePy."""
    tmp = Path(tempfile.mkdtemp())
    for i, frame in enumerate(frames):
        Image.fromarray(np.asarray(frame, dtype=np.uint8)).save(tmp / f"{i:04d}.png")
    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error",
                    "-framerate", str(fps), "-i", str(tmp / "%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-r", str(fps), str(path)], check=True)


def make_store(path) -> Store:
    """Store für den Test-Kanal 'sls' (Profil-Zeile wird mit angelegt)."""
    conn = ltm.init_db(path)
    ltm.upsert_channel(conn, "sls")
    conn.close()
    return Store(path, channel="sls")


class YoutubeIdTest(unittest.TestCase):
    def test_ids(self):
        self.assertEqual(youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
                         "dQw4w9WgXcQ")
        self.assertEqual(youtube_id("https://youtu.be/dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(youtube_id("https://www.youtube.com/shorts/abcDEF12345"),
                         "abcDEF12345")
        self.assertIsNone(youtube_id("https://example.com/x"))


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.store = make_store(self.tmp / "t.db")

    def tearDown(self):
        self.store.close()

    def test_empty_queue_requests_a_upload(self):
        self.assertEqual(self.store.next_work("sls")["action"], "request_upload")

    def test_fresh_source_needs_find(self):
        sid = self.store.add_source("https://youtu.be/abc", ext_id="abc", path="x.mp4",
                                    recipe="sls")
        nw = self.store.next_work("sls")
        self.assertEqual(nw["action"], "find")
        self.assertEqual(nw["source"]["id"], sid)

    def test_find_clip_then_find_again(self):
        sid = self.store.add_source("u", ext_id="v1", path="x.mp4", recipe="sls")
        self.assertEqual(self.store.next_work("sls")["action"], "find")
        ids = self.store.add_candidates(sid, [{"start": 1.0, "end": 5.0, "reason": "Tor"}])
        nw = self.store.next_work("sls")
        self.assertEqual(nw["action"], "clip")
        self.assertEqual(nw["clip"]["id"], ids[0])
        self.store.mark_clip(ids[0], "Used")
        # Ein verbrauchter Clip beendet das Video NICHT mehr.
        self.assertEqual(self.store.get_source(sid)["status"], "Downloaded")
        self.assertEqual(self.store.next_work("sls")["action"], "find")

    def test_skip_does_not_exhaust(self):
        sid = self.store.add_source("u", ext_id="skip", path="x.mp4", recipe="sls")
        ids = self.store.add_candidates(sid, [{"start": 1.0, "end": 5.0},
                                              {"start": 20.0, "end": 25.0}])
        self.store.mark_clip(ids[0], "Skipped")
        self.assertEqual(self.store.get_source(sid)["status"], "Downloaded")
        nw = self.store.next_work("sls")
        self.assertEqual(nw["action"], "clip")
        self.assertEqual(nw["clip"]["id"], ids[1])
        self.store.mark_clip(ids[1], "Skipped")
        self.assertEqual(self.store.get_source(sid)["status"], "Downloaded")
        self.assertEqual(self.store.next_work("sls")["action"], "find")

    def test_exhaust_stops_find(self):
        sid = self.store.add_source("u", ext_id="done", path="x.mp4", recipe="sls")
        self.store.set_source_status(sid, "Exhausted")
        self.assertEqual(self.store.next_work("sls")["action"], "request_upload")
        self.store.set_source_status(sid, "Downloaded")       # reopen
        self.assertEqual(self.store.next_work("sls")["action"], "find")

    def test_awaiting_upload_blocks_new_requests(self):
        sid = self.store.add_source("u", ext_id="pending", recipe="sls",
                                    status="AwaitingUpload")
        nw = self.store.next_work("sls")
        self.assertEqual(nw["action"], "await_upload")
        self.assertEqual(nw["source"]["id"], sid)
        # Kein path -> keine find-Arbeit, solange die Datei fehlt.
        self.assertEqual(self.store.get_source(sid)["status"], "AwaitingUpload")

    def test_set_source_file_finishes_the_handover(self):
        sid = self.store.add_source("u", ext_id="hand", recipe="sls",
                                    status="AwaitingUpload")
        got = self.store.set_source_file(sid, path="x.mp4", subs_path="x.vtt")
        self.assertEqual(got["status"], "Downloaded")
        self.assertEqual(got["path"], "x.mp4")
        self.assertEqual(self.store.next_work("sls")["action"], "find")

    def test_add_source_defaults_status_from_path(self):
        np_id = self.store.add_source("u", ext_id="np")
        self.assertEqual(self.store.get_source(np_id)["status"], "AwaitingUpload")
        wp_id = self.store.add_source("u", ext_id="wp", path="a.mp4")
        self.assertEqual(self.store.get_source(wp_id)["status"], "Downloaded")

    def test_new_candidates_revive_source(self):
        sid = self.store.add_source("u", ext_id="revive", path="x.mp4", recipe="sls")
        self.store.set_source_status(sid, "Exhausted")
        self.store.add_candidates(sid, [{"start": 3.0, "end": 8.0}])
        self.assertEqual(self.store.get_source(sid)["status"], "Downloaded")
        self.assertEqual(self.store.next_work("sls")["action"], "clip")

    def test_source_status_is_channel_scoped(self):
        with self.assertRaises(KeyError):
            self.store.set_source_status(999, "Exhausted")

    def test_next_is_per_recipe(self):
        sid = self.store.add_source("u", ext_id="r-a", path="a.mp4", recipe="sls")
        self.store.add_candidates(sid, [{"start": 1.0, "end": 5.0}])
        self.assertEqual(self.store.next_work("sls")["action"], "clip")
        # a different recipe must not see the SLS work
        self.assertEqual(self.store.next_work("other")["action"], "request_upload")

    def test_next_needs_a_recipe(self):
        with self.assertRaises(ValueError):
            self.store.next_work("")

    def test_recipe_set_and_filter(self):
        sid = self.store.add_source("u", ext_id="r-set", path="a.mp4")
        self.store.set_recipe(sid, "sls")
        self.assertEqual(self.store.get_source(sid)["recipe"], "sls")
        self.assertEqual([s["id"] for s in self.store.list_sources("sls")], [sid])
        self.assertEqual(self.store.list_sources("other"), [])

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
        self.store.add_candidates(sid, [{"start": 0, "end": 1}, {"start": 2, "end": 3}])
        row = self.store.list_sources()[0]
        self.assertEqual(row["candidates"], 2)
        self.assertEqual(row["used"], 0)

    def test_boxes_roundtrip(self):
        sid = self.store.add_source("u", ext_id="bx", path="x.mp4", recipe="sls")
        self.assertIsNone(self.store.get_boxes(sid))
        got = self.store.set_boxes(sid, {"score": [1200, 80, 180, 90]})
        self.assertEqual(got["boxes"], {"score": [1200, 80, 180, 90]})
        self.assertEqual(self.store.get_boxes(sid)["score"], [1200, 80, 180, 90])
        self.assertEqual(
            self.store.get_source(sid)["boxes"]["score"], [1200, 80, 180, 90])
        self.assertEqual(
            self.store.next_work("sls")["source"]["boxes"]["score"], [1200, 80, 180, 90])

    def test_bad_box_rejected(self):
        sid = self.store.add_source("u", ext_id="bx2", path="x.mp4")
        with self.assertRaises(ValueError):
            self.store.set_boxes(sid, {"score": [1, 2, 3]})
        with self.assertRaises(ValueError):
            self.store.set_boxes(sid, {"score": [1, 2, 0, 4]})


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
        store = make_store(self.tmp / "t.db")
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


class MotionProfileTest(unittest.TestCase):
    def test_static_clip_has_no_motion(self):
        tmp = Path(tempfile.mkdtemp())
        src = tmp / "static.mp4"
        write_video(src, [np.full((90, 160, 3), 20, dtype=np.uint8)] * 10, fps=10)
        got = motion.profile(src, start=0, end=1.0, fps=10)
        self.assertIsNone(got["first_motion"])
        self.assertIsNone(got["last_motion"])

    def test_moving_square_is_measured(self):
        tmp = Path(tempfile.mkdtemp())
        frames = []
        for i in range(20):
            frame = np.zeros((90, 160, 3), dtype=np.uint8)
            x = 10 + i * 7
            frame[30:60, x:x + 20] = 255
            frames.append(frame)
        src = tmp / "moving.mp4"
        write_video(src, frames, fps=10)
        got = motion.profile(src, start=0, end=2.0, fps=10, width=160)
        self.assertIsNotNone(got["first_motion"])
        self.assertLess(got["first_motion"], 0.6)
        self.assertGreater(got["last_motion"], 0.9)


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


class SegmentRenderTest(unittest.TestCase):
    def test_segments_span_and_store(self):
        store = make_store(Path(tempfile.mkdtemp()) / "t.db")
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
        write_video(video, [blank, with_score], fps=1)
        got = ocr.scan(video, (0, 0, 320, 107), [0.0, 1.0], step=1.0)
        self.assertEqual(got["checked"], 2)
        self.assertIsNotNone(got["first"])
        self.assertEqual(got["first"]["value"], 9.5)


class HandoverCliTest(unittest.TestCase):
    """request -> await_upload -> fetch (Operator lädt + hostet). Kein Netz."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.db = self.tmp / "t.db"
        make_store(self.db).close()
        self.env = mock.patch.dict(os.environ, {"BRAINROT_CHANNEL": "sls"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def _run(self, argv):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            yt_main(["--db", str(self.db), *argv])
        return json.loads(buf.getvalue())

    def test_request_creates_pending_source(self):
        got = self._run(["request", "--url", "https://youtu.be/abc123",
                         "--recipe", "sls"])
        self.assertEqual(got["action"], "request_upload")
        self.assertEqual(got["source_id"], 1)
        self.assertIn("abc123", got["url"])
        self.assertIn("Bucket", got["operator_message"])
        store = Store(self.db, channel="sls")
        try:
            self.assertEqual(store.get_source(1)["status"], "AwaitingUpload")
            self.assertEqual(store.next_work("sls")["action"], "await_upload")
        finally:
            store.close()

    def test_fetch_stores_the_file_and_opens_find(self):
        self._run(["request", "--url", "https://youtu.be/abc123", "--recipe", "sls"])
        out = self.tmp / "clips"

        def fake_download(url, dest=None, **kwargs):
            path = Path(dest)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"video")
            return {"path": str(path), "bytes": path.stat().st_size,
                    "filename": path.name, "url": url}

        def fake_transcribe(src, dest, **kwargs):
            Path(dest).write_text("WEBVTT\n", encoding="utf-8")
            return {"out": str(dest), "cues": 1, "words": 2, "model": "base",
                    "language": "en", "duration_s": 10.0}

        with mock.patch.object(cli_mod, "http_download", side_effect=fake_download), \
                mock.patch("editor.subtitles.transcribe", side_effect=fake_transcribe):
            got = self._run(["fetch", "--source", "1",
                             "--url", "https://bucket.example/abc123.mp4",
                             "--out-dir", str(out)])
        self.assertEqual(got["status"], "Downloaded")
        self.assertEqual(Path(got["file"]["path"]), out / "abc123.mp4")
        self.assertEqual(Path(got["subs"]), out / "abc123.vtt")
        self.assertEqual(got["transcript"]["cues"], 1)
        self.assertTrue((out / "abc123.mp4").is_file())
        store = Store(self.db, channel="sls")
        try:
            self.assertEqual(store.get_source(1)["subs_path"], str(out / "abc123.vtt"))
            self.assertEqual(store.next_work("sls")["action"], "find")
        finally:
            store.close()

    def test_fetch_can_skip_the_transcript(self):
        self._run(["request", "--url", "https://youtu.be/abc123", "--recipe", "sls"])
        out = self.tmp / "clips"

        def fake_download(url, dest=None, **kwargs):
            path = Path(dest)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"video")
            return {"path": str(path), "bytes": 5, "filename": path.name, "url": url}

        with mock.patch.object(cli_mod, "http_download", side_effect=fake_download):
            got = self._run(["fetch", "--source", "1",
                             "--url", "https://bucket.example/abc123.mp4",
                             "--out-dir", str(out), "--no-transcribe"])
        self.assertIsNone(got["subs"])
        self.assertEqual(got["status"], "Downloaded")


if __name__ == "__main__":
    unittest.main(verbosity=2)
