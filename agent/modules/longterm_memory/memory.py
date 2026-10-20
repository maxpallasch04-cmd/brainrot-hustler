"""Long-term memory: Python interface over the SQLite store.

One row per video, one lifecycle:

    planned  --markGenerated-->  generated  --upload-->  uploaded

Every instance belongs to exactly one channel::

    mem = LongTermMemory(channel="sls")

The channel profile (niche, recipes, upload tempo, quiet hours, ...) lives in
the ``channel`` table and is exposed as ``mem.profile``.

Public API (see README):
    addPlan, markGenerated, upload
    getVideo, listVideos, openCount, nextDue, overdue, task
"""

from __future__ import annotations

import time
from datetime import datetime
from enum import Enum
from pathlib import Path

from . import db

#: Fallback when a profile does not set `lead_h`.
DEFAULT_LEAD_S = 4 * 3600
#: Fallback when a profile does not set `open_target`.
DEFAULT_OPEN_TARGET = 2


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


def _hhmm(value: str) -> int | None:
    """'22:00' -> 1320 (minutes). ``None`` for empty/invalid."""
    if not value:
        return None
    try:
        hour, _, minute = str(value).partition(":")
        hour, minute = int(hour), int(minute or 0)
    except (TypeError, ValueError):
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour * 60 + minute


def _local(ts: int, tz_name: str) -> datetime:
    """Wall-clock time of `ts` in the channel timezone (local fallback)."""
    if tz_name:
        try:
            from zoneinfo import ZoneInfo

            return datetime.fromtimestamp(int(ts), ZoneInfo(tz_name))
        except Exception:  # no tzdata installed -> server local time
            pass
    return datetime.fromtimestamp(int(ts))


def in_quiet_hours(ts: int, start: str, end: str, tz_name: str = "") -> bool:
    """True if `ts` falls into the quiet window (supports wrap past midnight)."""
    a, b = _hhmm(start), _hhmm(end)
    if a is None or b is None or a == b:
        return False
    dt = _local(ts, tz_name)
    minute = dt.hour * 60 + dt.minute
    if a < b:
        return a <= minute < b
    return minute >= a or minute < b


class LongTermMemory:
    """Channel-scoped access to the plan. One connection per instance."""

    def __init__(self, path: str | Path | None = None, *, channel: str) -> None:
        channel = str(channel or "").strip().lower()
        if not channel:
            raise db.ChannelError("channel is required (e.g. channel='sls')")
        self.conn = db.init_db(path)
        self.channel = channel
        try:
            self.profile = db.require_channel(self.conn, channel)
        except Exception:
            self.conn.close()
            raise

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "LongTermMemory":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---- profile --------------------------------------------------------

    @property
    def open_target(self) -> int:
        return int(self.profile.get("open_target") or DEFAULT_OPEN_TARGET)

    @property
    def lead_s(self) -> int:
        return int(float(self.profile.get("lead_h") or 0) * 3600) or DEFAULT_LEAD_S

    def quiet_hours(self) -> tuple[str, str, str]:
        return (self.profile.get("quiet_start", ""),
                self.profile.get("quiet_end", ""),
                self.profile.get("tz", ""))

    # ---- plan -----------------------------------------------------------

    def addPlan(
        self,
        idea: str,
        recipe: str,
        plan_at: int,
        *,
        art: VideoArt | str | None = None,
        theme: str = "",
    ) -> int:
        """Insert a `planned` entry (no file yet) and return its id."""
        if not idea.strip():
            raise ValueError("idea must not be empty")
        if not recipe.strip():
            raise ValueError("recipe must not be empty")
        recipe = recipe.strip()

        allowed = self.profile.get("recipes") or []
        if allowed and recipe not in allowed:
            raise ValueError(
                f"recipe {recipe!r} is not active for channel {self.channel!r} "
                f"(allowed: {', '.join(allowed)})"
            )

        start, end, tz = self.quiet_hours()
        if in_quiet_hours(int(plan_at), start, end, tz):
            raise ValueError(
                f"plan_at {plan_at} is inside the quiet hours {start}-{end} "
                f"({tz or 'local'}) for channel {self.channel!r}"
            )

        art_value = _art(art) if art is not None else (self.profile.get("art") or VideoArt.YT_CLIP.value)
        cur = self.conn.execute(
            """INSERT INTO video (channel_id, idea, title, recipe, art, theme,
                                  len_s, plan_at, created_at, status)
               VALUES (?, ?, '', ?, ?, ?, 0, ?, ?, ?)""",
            (self.channel, idea.strip(), recipe, art_value, theme,
             int(plan_at), _now(), Status.PLANNED.value),
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
        row = self._require(video_id)
        if row["status"] == Status.UPLOADED.value:
            raise ValueError(f"video {video_id} is already uploaded")
        if not file.strip():
            raise ValueError("file must not be empty")
        self.conn.execute(
            """UPDATE video
                  SET title = ?, description = ?, file = ?, len_s = ?,
                      art = COALESCE(?, art), theme = COALESCE(?, theme),
                      status = ?
                WHERE id = ? AND channel_id = ?""",
            (title.strip(), description, file.strip(), int(len_s),
             _art(art) if art is not None else None, theme,
             Status.GENERATED.value, int(video_id), self.channel),
        )
        self.conn.commit()

    def upload(self, video_id: int, at: int | None = None) -> None:
        """Mark a video as uploaded and record the upload time. Idempotent."""
        row = self._require(video_id)
        if row["status"] == Status.UPLOADED.value:
            return  # already uploaded -> keep original upload_at
        self.conn.execute(
            "UPDATE video SET status = ?, upload_at = ? WHERE id = ? AND channel_id = ?",
            (Status.UPLOADED.value, _now() if at is None else int(at),
             int(video_id), self.channel),
        )
        self.conn.commit()

    # ---- queries --------------------------------------------------------

    def getVideo(self, video_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM video WHERE id = ? AND channel_id = ?",
            (int(video_id), self.channel),
        ).fetchone()
        return dict(row) if row else None

    def listVideos(self, status: Status | str | None = None) -> list[dict]:
        sql, args = "SELECT * FROM video WHERE channel_id = ?", [self.channel]
        if status is not None:
            sql += " AND status = ?"
            args.append(_status(status))
        sql += " ORDER BY COALESCE(plan_at, created_at), id"
        return [dict(r) for r in self.conn.execute(sql, args)]

    def openCount(self) -> int:
        """Entries still on the plan: `planned` + `generated`."""
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM video WHERE channel_id = ? AND status IN (?, ?)",
            (self.channel, Status.PLANNED.value, Status.GENERATED.value),
        ).fetchone()
        return int(row["n"])

    def nextDue(self, now: int | None = None,
                lead_s: int | None = None) -> dict | None:
        """Earliest `planned` entry whose upload time is within the lead window."""
        lead_s = self.lead_s if lead_s is None else int(lead_s)
        base = int(now) if now is not None else _now()
        row = self.conn.execute(
            """SELECT * FROM video
                WHERE channel_id = ? AND status = ? AND plan_at IS NOT NULL
                  AND plan_at <= ?
                ORDER BY plan_at, id LIMIT 1""",
            (self.channel, Status.PLANNED.value, base + lead_s),
        ).fetchone()
        return dict(row) if row else None

    def overdue(self, now: int | None = None) -> list[dict]:
        """Generated videos whose planned upload time has passed."""
        now = int(now) if now is not None else _now()
        return [dict(r) for r in self.conn.execute(
            """SELECT * FROM video
                WHERE channel_id = ? AND status = ? AND plan_at IS NOT NULL
                  AND plan_at <= ?
                ORDER BY plan_at, id""",
            (self.channel, Status.GENERATED.value, now),
        )]

    def task(self, now: int | None = None, lead_s: int | None = None,
             open_target: int | None = None) -> dict:
        """One heartbeat decision: `upload` | `pipeline` | `plan` | `idle`.

        Priority: upload (upload time passed) -> pipeline (entry due) -> plan
        (queue too short). Everything that is also pending lands in `also`,
        the matching payload in `entry` / `videos`.
        """
        now = int(now) if now is not None else _now()
        open_n = self.openCount()
        due = self.nextDue(now, lead_s)
        over = self.overdue(now)
        target = self.open_target if open_target is None else int(open_target)

        pending = []
        if over:
            pending.append("upload")
        if due is not None:
            pending.append("pipeline")
        if open_n < target:
            pending.append("plan")

        out: dict = {
            "channel": self.channel,
            "action": pending[0] if pending else "idle",
            "open": open_n,
            "target": target,
            "also": pending[1:],
        }
        if due is not None:
            out["entry"] = due
        if over:
            out["videos"] = over
        return out

    # ---- internals ------------------------------------------------------

    def _require(self, video_id: int) -> dict:
        row = self.getVideo(video_id)
        if row is None:
            raise KeyError(
                f"video {video_id} not found in channel {self.channel!r}"
            )
        return row
