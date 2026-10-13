"""Smoke tests for the long-term memory. Run: python3 tests/test_longterm_memory.py"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from longterm_memory import LongTermMemory, Status, VideoArt, db  # noqa: E402


class LongTermMemoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mem = LongTermMemory(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.mem.close()
        self.tmp.cleanup()

    def test_add_and_get(self):
        vid = self.mem.addVideo("hello", VideoArt.GEKLAUT, len_s=12, theme="cats")
        row = self.mem.getVideo(vid)
        self.assertEqual(row["title"], "hello")
        self.assertEqual(row["art"], "Geklaut")
        self.assertEqual(row["status"], Status.CREATED.value)
        self.assertIsNone(row["upload_at"])
        self.assertEqual(row["recipe"], "")
        self.assertEqual(len(self.mem.listVideos()), 1)

    def test_upload(self):
        vid = self.mem.addVideo("v", VideoArt.SELBSTGENERIERT, len_s=8)
        self.mem.upload(vid, at=1000)
        row = self.mem.getVideo(vid)
        self.assertEqual(row["status"], Status.UPLOADED.value)
        self.assertEqual(row["upload_at"], 1000)
        self.mem.upload(vid, at=2000)          # idempotent
        self.assertEqual(self.mem.getVideo(vid)["upload_at"], 1000)

    def test_metrics(self):
        vid = self.mem.addVideo("v", VideoArt.TWITCH_CLIP, len_s=20)
        self.mem.addMetric(vid, 100, 1, 5, ts=10)
        self.mem.addMetric(vid, 300, 3, 9, ts=20)
        self.assertEqual(self.mem.newestMetric(vid)["views"], 300)
        self.assertEqual(len(self.mem.listMetrics(vid)), 2)
        self.mem.addMetric(vid, 999, 9, 9, ts=20)      # overwrite same ts
        self.assertEqual(self.mem.newestMetric(vid)["views"], 999)
        self.assertEqual(len(self.mem.listMetrics(vid)), 2)
        self.assertEqual(self.mem.totalSince(0)["views"], 100 + 999)

    def test_recipe_field(self):
        vid = self.mem.addVideo("hello", VideoArt.TWITCH_CLIP, len_s=12,
                                theme="cats", recipe="twitchkatze")
        self.assertEqual(self.mem.getVideo(vid)["recipe"], "twitchkatze")
        plain = self.mem.addVideo("x", VideoArt.GEKLAUT, len_s=5)
        self.assertEqual(self.mem.getVideo(plain)["recipe"], "")

    def test_recipe_migration(self):
        # A DB from the older schema (no `recipe` column) must gain it on init.
        path = Path(self.tmp.name) / "old.db"
        conn = db.connect(path)
        conn.executescript(
            "CREATE TABLE video (id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',"
            " art TEXT NOT NULL, len_s INTEGER NOT NULL,"
            " theme TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL,"
            " upload_at INTEGER, status TEXT NOT NULL DEFAULT 'Created');"
        )
        conn.commit()
        conn.close()
        mem = LongTermMemory(path)
        try:
            vid = mem.addVideo("m", VideoArt.TWITCH_CLIP, len_s=3, recipe="r1")
            self.assertEqual(mem.getVideo(vid)["recipe"], "r1")
        finally:
            mem.close()

    def test_unknown_video(self):
        with self.assertRaises(KeyError):
            self.mem.upload(999)
        with self.assertRaises(KeyError):
            self.mem.addMetric(999, 0, 0, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
