"""Long-term memory: Python interface over the SQLite store.

One row per video, one lifecycle:

    planned  --markGenerated-->  generated  --upload-->  uploaded

Public API (see README):
    addPlan, markGenerated, upload
    getVideo, listVideos, openCount, nextDue, overdue
"""

from __future__ import annotations

import time
from enum import Enum
from pathlib import Path

from . import db

#: A `planned` entry becomes due this long before its upload time.
DEFAULT_LEAD_S = 4 * 3600


class Status(str, Enum):
    PLANNED = "planned"
    GENERATED = "generated"
    UPLOADED = "uploaded"


class VideoArt(str, Enum):
    SELBSTGENERIERT = "Selbstgeneriert"
    TWITCH_CLIP = "Twitch-Clip"
    YT_CLIP = "YT-Clip"


def _now() -> int:
    return int(time.time())


def _art(value: VideoArt | str) -> str:
    return value.value if isinstance(value, VideoArt) else VideoArt(value).value


def _status(value: Status | str) -> str:
    return value.value if isinstance(value, Status) else Status(value).value


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

    # ---- plan -----------------------------------------------------------

    def addPlan(
        self,
        idea: str,
        recipe: str,
        plan_at: int,
        *,
        art: VideoArt | str = VideoArt.YT_CLIP,
        theme: str = "",
    ) -> int:
        """Insert a `planned` entry (no file yet) and return its id."""
        if not idea.strip():
            raise ValueError("idea must not be empty")
        if not recipe.strip():
            raise ValueError("recipe must not be empty")
        cur = self.conn.execute(
            """INSERT INTO video (idea, title, recipe, art, theme, len_s, plan_at, created_at, status)
               VALUES (?, '', ?, ?, ?, 0, ?, ?, ?)""",
            (idea.strip(), recipe.strip(), _art(art), theme, int(plan_at),
             _now(), Status.PLANNED.value),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def markGenerated(
        self,
        video_id: int,
        *,
        title: str,
        description: str = "",
        file: str,
        len_s: int,
        art: VideoArt | str | None = None,
        theme: str | None = None,
    ) -> None:
        """Attach the render: title, caption, file path, duration -> `generated`."""
        self._require(video_id)
        row = self.getVideo(video_id)
        if row["status"] == Status.UPLOADED.value:
            raise ValueError(f"video {video_id} is already uploaded")
        if not file.strip():
            raise ValueError("file must not be empty")
        self.conn.execute(
            """UPDATE video
                  SET title = ?, description = ?, file = ?, len_s = ?,
                      art = COALESCE(?, art), theme = COALESCE(?, theme),
                      status = ?
                WHERE id = ?""",
            (title.strip(), description, file.strip(), int(len_s),
             _art(art) if art is not None else None, theme,
             Status.GENERATED.value, int(video_id)),
        )
        self.conn.commit()

    def upload(self, video_id: int, at: int | None = None) -> None:
        """Mark a video as uploaded and record the upload time. Idempotent."""
        self._require(video_id)
        row = self.getVideo(video_id)
        if row["status"] == Status.UPLOADED.value:
            return  # already uploaded -> keep original upload_at
        self.conn.execute(
            "UPDATE video SET status = ?, upload_at = ? WHERE id = ?",
            (Status.UPLOADED.value, _now() if at is None else int(at), int(video_id)),
        )
        self.conn.commit()

    # ---- queries --------------------------------------------------------

    def getVideo(self, video_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM video WHERE id = ?", (int(video_id),)
        ).fetchone()
        return dict(row) if row else None

    def listVideos(self, status: Status | str | None = None) -> list[dict]:
        sql, args = "SELECT * FROM video", ()
        if status is not None:
            sql += " WHERE status = ?"
            args = (_status(status),)
        sql += " ORDER BY COALESCE(plan_at, created_at), id"
        return [dict(r) for r in self.conn.execute(sql, args)]

    def openCount(self) -> int:
        """Entries still on the plan: `planned` + `generated`."""
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM video WHERE status IN (?, ?)",
            (Status.PLANNED.value, Status.GENERATED.value),
        ).fetchone()
        return int(row["n"])

    def nextDue(self, now: int | None = None,
                lead_s: int = DEFAULT_LEAD_S) -> dict | None:
        """Earliest `planned` entry whose upload time is within `lead_s`."""
        row = self.conn.execute(
            """SELECT * FROM video
                WHERE status = ? AND plan_at IS NOT NULL AND plan_at <= ?
                ORDER BY plan_at, id LIMIT 1""",
            (Status.PLANNED.value, (int(now) if now is not None else _now()) + int(lead_s)),
        ).fetchone()
        return dict(row) if row else None

    def overdue(self, now: int | None = None) -> list[dict]:
        """Generated videos whose planned upload time has passed."""
        now = int(now) if now is not None else _now()
        return [dict(r) for r in self.conn.execute(
            """SELECT * FROM video
                WHERE status = ? AND plan_at IS NOT NULL AND plan_at <= ?
                ORDER BY plan_at, id""",
            (Status.GENERATED.value, now),
        )]

    def task(self, now: int | None = None, lead_s: int = DEFAULT_LEAD_S,
             open_target: int = 2) -> dict:
        """One heartbeat decision: `upload` | `pipeline` | `plan` | `idle`.

        Priority: upload (upload time passed) -> pipeline (entry due) -> plan
        (queue too short). Everything that is also pending lands in `also`,
        the matching payload in `entry` / `videos`.
        """
        now = int(now) if now is not None else _now()
        open_n = self.openCount()
        due = self.nextDue(now, lead_s)
        over = self.overdue(now)

        pending = []
        if over:
            pending.append("upload")
        if due is not None:
            pending.append("pipeline")
        if open_n < int(open_target):
            pending.append("plan")

        out: dict = {
            "action": pending[0] if pending else "idle",
            "open": open_n,
            "target": int(open_target),
            "also": pending[1:],
        }
        if due is not None:
            out["entry"] = due
        if over:
            out["videos"] = over
        return out

    # ---- internals ------------------------------------------------------

    def _require(self, video_id: int) -> None:
        if self.conn.execute("SELECT 1 FROM video WHERE id = ?", (int(video_id),)).fetchone() is None:
            raise KeyError(f"video {video_id} not found")
