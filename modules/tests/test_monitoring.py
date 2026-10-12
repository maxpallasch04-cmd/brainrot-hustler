"""Offline unit tests for the monitoring layer (no network).

Run: python3 tests/test_monitoring.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from longterm_memory import LongTermMemory, VideoArt  # noqa: E402
from monitoring import analysis, metrics  # noqa: E402
from monitoring.store import ReportStore  # noqa: E402

G0 = {"views": 0, "comments": 0, "likes": 0}


class AnalysisTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mem = LongTermMemory(Path(self.tmp.name) / "mem.db")

    def tearDown(self):
        self.mem.close()
        self.tmp.cleanup()

    def _vid(self, title, upload_at):
        vid = self.mem.addVideo(title, VideoArt.TWITCH_CLIP, 20)
        self.mem.upload(vid, at=upload_at)
        return vid

    def test_report_math(self):
        a = self._vid("A", 900)
        r1 = analysis.build_report(self.mem, {a: {"views": 100, "comments": 0, "likes": 0}},
                                   {"views": 100, "comments": 0, "likes": 0}, [], now=1000)
        self.assertEqual(r1["N"], 1)
        self.assertEqual(r1["V_0"], {a: {"views": 100, "comments": 0, "likes": 0}})
        self.assertIsNone(r1["d_global"]["views"])

        b = self._vid("B", 1500)
        r2 = analysis.build_report(
            self.mem,
            {a: {"views": 300, "comments": 0, "likes": 0},
             b: {"views": 50, "comments": 0, "likes": 0}},
            {"views": 350, "comments": 0, "likes": 0}, [r1], now=2000)
        self.assertEqual(r2["N"], 1)
        self.assertEqual(set(r2["V_0"]), {b})
        self.assertEqual(set(r2["V_1"]), {a})
        self.assertAlmostEqual(r2["d_video"][a]["views"], 2.0)  # (300-100)/100

        r3 = analysis.build_report(
            self.mem,
            {a: {"views": 600, "comments": 0, "likes": 0},
             b: {"views": 200, "comments": 0, "likes": 0}},
            {"views": 800, "comments": 0, "likes": 0}, [r1, r2], now=3000)
        self.assertEqual(r3["N"], 0)
        self.assertEqual(set(r3["V_1"]), {b})
        self.assertAlmostEqual(r3["d_global"]["views"], (800 - 350) / (350 - 100))
        self.assertAlmostEqual(r3["d_video"][b]["views"], 3.0)  # (200-50)/50

    def test_blowups(self):
        old = self._vid("OLD", 10)
        r1 = {"ts": 1000, "G": G0}
        r2 = {"ts": 2000, "G": G0}
        new = self._vid("NEW", 2500)
        report = analysis.build_report(
            self.mem,
            {old: {"views": 9000, "comments": 0, "likes": 0},
             new: {"views": 100, "comments": 0, "likes": 0}},
            {"views": 9100, "comments": 0, "likes": 0}, [r1, r2], now=3000)
        self.assertEqual(report["N"], 1)
        self.assertEqual(report["blowups"], [old])

    def test_match_by_title_and_time(self):
        titled = self._vid("Hello", 1000)
        blank = self.mem.addVideo("", VideoArt.TWITCH_CLIP, 10)
        self.mem.upload(blank, at=5000)

        matched, unmatched = analysis.match_videos(self.mem, [
            {"id": "t1", "title": "Hello", "view_count": 11, "comment_count": 1, "like_count": 2},
            {"id": "t2", "title": "", "create_time": 5100, "view_count": 7, "comment_count": 0, "like_count": 0},
            {"id": "t3", "title": "nope", "create_time": 1, "view_count": 3, "comment_count": 0, "like_count": 0},
        ])
        self.assertEqual(matched[titled], {"views": 11, "comments": 1, "likes": 2})
        self.assertEqual(matched[blank], {"views": 7, "comments": 0, "likes": 0})
        self.assertEqual([v["id"] for v in unmatched], ["t3"])

    def test_run_analysis_persists(self):
        a = self._vid("A", 1000)
        store = ReportStore(Path(self.tmp.name) / "rep.db")
        try:
            result = analysis.run_analysis(self.mem, [
                {"id": "tt1", "title": "A", "create_time": 1000,
                 "view_count": 100, "comment_count": 5, "like_count": 10},
            ], store, now=2000)
            self.assertEqual(result["report"]["N"], 1)
            self.assertEqual(result["unmatched"], [])
            self.assertEqual(self.mem.newestMetric(a)["views"], 100)
            self.assertEqual(store.recent(5)[0]["ts"], 2000)
        finally:
            store.close()


class StoreTest(unittest.TestCase):
    def test_append_and_recent(self):
        with tempfile.TemporaryDirectory() as tmp:
            with ReportStore(Path(tmp) / "rep.db") as store:
                for ts in (1, 2, 3):
                    store.append({"ts": ts, "G": G0})
                self.assertEqual([r["ts"] for r in store.recent(2)], [2, 3])
                self.assertEqual(len(store.all()), 3)


class MetricsTest(unittest.TestCase):
    def test_missing_token(self):
        with mock.patch.dict(os.environ, {"TIKTOK_ACCESS_TOKEN": ""}):
            with self.assertRaises(RuntimeError):
                metrics.TikTokMetrics()

    def test_list_videos_and_user_stats(self):
        calls = []

        def fake(url, *, method="GET", headers=None, body=None, timeout=15):
            calls.append((url, method))
            if "/video/list/" in url:
                return {"data": {"videos": [{"id": "1", "view_count": 5}],
                                 "cursor": "", "has_more": False}}
            return {"data": {"user": {"follower_count": 7, "likes_count": 9,
                                      "video_count": 3}}}

        with mock.patch.object(metrics, "_request", fake):
            client = metrics.TikTokMetrics("tok")
            vids, cursor, has_more = client.list_videos()
            stats = client.user_stats()

        self.assertEqual(vids[0]["id"], "1")
        self.assertFalse(has_more)
        self.assertEqual(stats["follower_count"], 7)
        self.assertTrue(any("/video/list/" in u for u, _ in calls))

    def test_list_recent_pages_until_done(self):
        pages = [
            {"data": {"videos": [{"id": str(i)} for i in range(20)],
                      "cursor": "c1", "has_more": True}},
            {"data": {"videos": [{"id": "x"}], "cursor": "", "has_more": False}},
        ]
        seen = []

        def fake(url, *, method="GET", headers=None, body=None, timeout=15):
            seen.append(body.get("cursor"))
            return pages[min(len(seen) - 1, len(pages) - 1)]

        with mock.patch.object(metrics, "_request", fake):
            videos = metrics.TikTokMetrics("tok").list_recent(50)
        self.assertEqual(len(videos), 21)
        self.assertIsNone(seen[0])
        self.assertEqual(seen[1], "c1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
