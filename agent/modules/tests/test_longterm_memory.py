"""Smoke tests for the long-term memory. Run: python3 tests/test_longterm_memory.py"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from longterm_memory import LongTermMemory, Status, VideoArt, db  # noqa: E402

NOW = 1_800_000_000
H = 3600


class LongTermMemoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mem = LongTermMemory(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.mem.close()
        self.tmp.cleanup()

    def test_add_plan(self):
        vid = self.mem.addPlan("Best Trick, Score 9.1", "ytsls-besttrick",
                               plan_at=NOW + 24 * H, theme="sls")
        row = self.mem.getVideo(vid)
        self.assertEqual(row["status"], Status.PLANNED.value)
        self.assertEqual(row["idea"], "Best Trick, Score 9.1")
        self.assertEqual(row["recipe"], "ytsls-besttrick")
        self.assertEqual(row["plan_at"], NOW + 24 * H)
        self.assertEqual(row["art"], "YT-Clip")
        self.assertEqual(row["len_s"], 0)
        self.assertIsNone(row["file"])
        self.assertIsNone(row["upload_at"])
        self.assertEqual(self.mem.openCount(), 1)

    def test_add_plan_validation(self):
        with self.assertRaises(ValueError):
            self.mem.addPlan("  ", "r", plan_at=NOW)
        with self.assertRaises(ValueError):
            self.mem.addPlan("idea", "", plan_at=NOW)

    def test_next_due_respects_lead(self):
        far = self.mem.addPlan("later", "r", plan_at=NOW + 10 * H)
        self.assertIsNone(self.mem.nextDue(NOW))
        near = self.mem.addPlan("soon", "r", plan_at=NOW + 3 * H)
        self.assertEqual(self.mem.nextDue(NOW)["id"], near)
        self.assertEqual(self.mem.nextDue(NOW, lead_s=24 * H)["id"], near)
        self.assertNotEqual(far, near)

    def test_generated_then_uploaded(self):
        vid = self.mem.addPlan("idea", "r", plan_at=NOW, art=VideoArt.YT_CLIP)
        self.mem.markGenerated(vid, title="Best Trick", description="caption",
                               file="memory/videos/x.mp4", len_s=31)
        row = self.mem.getVideo(vid)
        self.assertEqual(row["status"], Status.GENERATED.value)
        self.assertEqual(row["title"], "Best Trick")
        self.assertEqual(row["file"], "memory/videos/x.mp4")
        self.assertEqual(row["len_s"], 31)
        self.assertEqual(row["idea"], "idea")
        self.assertEqual(self.mem.openCount(), 1)
        self.assertIsNone(self.mem.nextDue(NOW))          # no longer planned
        self.assertEqual(len(self.mem.overdue(NOW)), 1)

        self.mem.upload(vid, at=1234)
        row = self.mem.getVideo(vid)
        self.assertEqual(row["status"], Status.UPLOADED.value)
        self.assertEqual(row["upload_at"], 1234)
        self.assertEqual(self.mem.openCount(), 0)
        self.assertEqual(self.mem.overdue(NOW), [])
        self.mem.upload(vid, at=9999)                     # idempotent
        self.assertEqual(self.mem.getVideo(vid)["upload_at"], 1234)

    def test_generated_requires_file(self):
        vid = self.mem.addPlan("idea", "r", plan_at=NOW)
        with self.assertRaises(ValueError):
            self.mem.markGenerated(vid, title="t", file="", len_s=10)

    def test_task_decision(self):
        # empty DB -> plan
        t = self.mem.task(NOW)
        self.assertEqual(t["action"], "plan")
        self.assertEqual((t["open"], t["target"]), (0, 2))
        self.assertNotIn("entry", t)

        # one open entry, nothing due -> plan
        a = self.mem.addPlan("a", "r", plan_at=NOW + 48 * H)
        self.assertEqual(self.mem.task(NOW)["action"], "plan")

        # second open entry, nothing due -> idle
        b = self.mem.addPlan("b", "r", plan_at=NOW + 72 * H)
        t = self.mem.task(NOW)
        self.assertEqual(t["action"], "idle")
        self.assertEqual(t["open"], 2)

        # due entry -> pipeline, entry included
        self.mem.conn.execute("UPDATE video SET plan_at = ? WHERE id = ?", (NOW + H, b))
        self.mem.conn.commit()
        t = self.mem.task(NOW)
        self.assertEqual(t["action"], "pipeline")
        self.assertEqual(t["entry"]["id"], b)

        # generated + overdue -> upload
        self.mem.markGenerated(a, title="T", file="memory/videos/a.mp4", len_s=10)
        self.mem.conn.execute("UPDATE video SET plan_at = ? WHERE id = ?", (NOW - H, a))
        self.mem.conn.commit()
        t = self.mem.task(NOW, open_target=2)
        self.assertEqual(t["action"], "upload")
        self.assertEqual(t["also"], ["pipeline"])
        self.assertEqual([v["id"] for v in t["videos"]], [a])

        # nothing overdue anymore -> pipeline is the action
        self.mem.upload(a, at=NOW)
        t = self.mem.task(NOW, open_target=2)
        self.assertEqual(t["action"], "pipeline")
        self.assertEqual(t["also"], ["plan"])

        # only planning left -> plan
        t = self.mem.task(NOW, open_target=2, lead_s=0)
        self.assertEqual(t["action"], "plan")
        self.assertNotIn("videos", t)

        # nothing open, nothing due -> idle
        self.mem.upload(b, at=NOW)
        self.assertEqual(self.mem.task(NOW, open_target=0)["action"], "idle")

    def test_open_count(self):
        self.assertEqual(self.mem.openCount(), 0)
        vid = self.mem.addPlan("a", "r", plan_at=NOW)
        self.assertEqual(self.mem.openCount(), 1)
        self.mem.markGenerated(vid, title="T", file="f.mp4", len_s=5)
        self.assertEqual(self.mem.openCount(), 1)
        self.mem.upload(vid)
        self.assertEqual(self.mem.openCount(), 0)

    def test_unknown_video(self):
        with self.assertRaises(KeyError):
            self.mem.upload(999)
        with self.assertRaises(KeyError):
            self.mem.markGenerated(999, title="t", file="f.mp4", len_s=1)

    def test_v1_migration(self):
        # v1: old columns, `Created`/`Uploaded` statuses, metric table.
        path = Path(self.tmp.name) / "old.db"
        conn = db.connect(path)
        conn.executescript(
            "CREATE TABLE video (id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',"
            " art TEXT NOT NULL, len_s INTEGER NOT NULL,"
            " theme TEXT NOT NULL DEFAULT '', recipe TEXT NOT NULL DEFAULT '',"
            " created_at INTEGER NOT NULL, upload_at INTEGER,"
            " status TEXT NOT NULL DEFAULT 'Created');"
            "CREATE TABLE metric (id INTEGER PRIMARY KEY, video_id INTEGER,"
            " ts INTEGER, views INTEGER, comments INTEGER, likes INTEGER);"
            "INSERT INTO video (title, art, len_s, created_at, status)"
            " VALUES ('alt', 'YT-Clip', 30, 100, 'Created');"
            "INSERT INTO metric (video_id, ts, views, comments, likes)"
            " VALUES (1, 1, 5, 0, 0);"
        )
        conn.commit()
        conn.close()

        mem = LongTermMemory(path)
        try:
            self.assertEqual(mem.getVideo(1)["status"], "generated")
            tables = {r["name"] for r in mem.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertNotIn("metric", tables)
            vid = mem.addPlan("neu", "r", plan_at=NOW)
            self.assertEqual(mem.getVideo(vid)["status"], "planned")
            self.assertEqual(mem.openCount(), 2)
        finally:
            mem.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
