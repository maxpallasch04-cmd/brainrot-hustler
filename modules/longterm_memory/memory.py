"""Long-term memory: Python interface over the SQLite store.

Public API (see README):
    addVideo, getVideo, listVideos, listMetrics
    upload, addMetric, newestMetric
    videosUploadedSince, totalSince
"""

from __future__ import annotations

import time
from enum import Enum
from pathlib import Path

from . import db


class Status(str, Enum):
    CREATED = "Created"
    UPLOADED = "Uploaded"


class VideoArt(str, Enum):
    SELBSTGENERIERT = "Selbstgeneriert"
    TWITCH_CLIP = "Twitch-Clip"
    YT_CLIP = "YT-Clip"


def _now() -> int:
    return int(time.time())


def _art(value: VideoArt | str) -> str:
    return value.value if isinstance(value, VideoArt) else VideoArt(value).value


class LongTermMemory:
    """Thin, honest wrapper around the SQLite store. One connection per instance."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.conn = db.init_db(path)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "LongTermMemory":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---- videos ---------------------------------------------------------

    def addVideo(
        self,
        title: str,
        art: VideoArt | str,
        len_s: int,
        description: str = "",
        theme: str = "",
        recipe: str = "",
        created_at: int | None = None,
    ) -> int:
        """Insert a video (status Created) and return its id."""
        cur = self.conn.execute(
            """INSERT INTO video (title, description, art, len_s, theme, recipe, created_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, description, _art(art), int(len_s), theme, recipe,
             _now() if created_at is None else int(created_at), Status.CREATED.value),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def getVideo(self, video_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM video WHERE id = ?", (int(video_id),)
        ).fetchone()
        return dict(row) if row else None

    def listVideos(self, status: Status | str | None = None) -> list[dict]:
        sql, args = "SELECT * FROM video", ()
        if status is not None:
            sql += " WHERE status = ?"
            args = (status.value if isinstance(status, Status) else str(status),)
        sql += " ORDER BY id"
        return [dict(r) for r in self.conn.execute(sql, args)]

    # ---- core interface -------------------------------------------------

    def upload(self, video_id: int, at: int | None = None) -> None:
        """Mark a video as Uploaded and record the upload time. Idempotent."""
        self._require(video_id)
        row = self.getVideo(video_id)
        if row["status"] == Status.UPLOADED.value:
            return  # already uploaded -> keep original upload_at
        self.conn.execute(
            "UPDATE video SET status = ?, upload_at = ? WHERE id = ?",
            (Status.UPLOADED.value, _now() if at is None else int(at), int(video_id)),
        )
        self.conn.commit()

    def addMetric(
        self, video_id: int, views: int, comments: int, likes: int, ts: int | None = None
    ) -> None:
        """Append a metric snapshot; same (video_id, ts) overwrites."""
        self._require(video_id)
        ts = _now() if ts is None else int(ts)
        self.conn.execute(
            """INSERT INTO metric (video_id, ts, views, comments, likes)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (video_id, ts) DO UPDATE SET
                   views = excluded.views,
                   comments = excluded.comments,
                   likes = excluded.likes""",
            (int(video_id), ts, int(views), int(comments), int(likes)),
        )
        self.conn.commit()

    def newestMetric(self, video_id: int) -> dict | None:
        """Newest metric snapshot for a video, or None."""
        row = self.conn.execute(
            "SELECT * FROM metric WHERE video_id = ? ORDER BY ts DESC LIMIT 1",
            (int(video_id),),
        ).fetchone()
        return dict(row) if row else None

    # ---- read helpers ---------------------------------------------------

    def listMetrics(self, video_id: int, limit: int | None = None) -> list[dict]:
        """Metric history for a video, oldest first."""
        sql = "SELECT * FROM metric WHERE video_id = ? ORDER BY ts"
        args: tuple = (int(video_id),)
        if limit is not None:
            sql = ("SELECT * FROM (SELECT * FROM metric WHERE video_id = ? "
                   "ORDER BY ts DESC LIMIT ?) ORDER BY ts")
            args = (int(video_id), int(limit))
        return [dict(r) for r in self.conn.execute(sql, args)]

    def videosUploadedSince(self, ts: int) -> list[dict]:
        """Videos uploaded at or after `ts`."""
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM video WHERE upload_at IS NOT NULL AND upload_at >= ? "
            "ORDER BY upload_at",
            (int(ts),),
        )]

    def totalSince(self, ts: int) -> dict:
        """G = summed metrics over all snapshots taken at or after `ts`."""
        row = self.conn.execute(
            "SELECT COALESCE(SUM(views),0) v, COALESCE(SUM(comments),0) c, "
            "COALESCE(SUM(likes),0) l FROM metric WHERE ts >= ?",
            (int(ts),),
        ).fetchone()
        return {"views": row["v"], "comments": row["c"], "likes": row["l"]}

    # ---- internals ------------------------------------------------------

    def _require(self, video_id: int) -> None:
        if self.conn.execute("SELECT 1 FROM video WHERE id = ?", (int(video_id),)).fetchone() is None:
            raise KeyError(f"video {video_id} not found")
