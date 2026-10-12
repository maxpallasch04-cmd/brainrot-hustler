"""SQLite state for the YT-clip art: source videos + candidate clips.

Shares the project DB (``data/brainrot.db`` / ``BRAINROT_DB``) with
``longterm_memory`` but owns its own tables: ``yt_source``, ``yt_clip``.

State machine
-------------
``yt_source.status``:  Downloaded  -> no format yet (step: format)
                       Formatted   -> has format, clips possible (steps: find/clip)
                       Exhausted   -> nothing left to clip
``yt_clip.status``:    Candidate -> Used | Skipped
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

DEFAULT_DB = Path(
    os.environ.get("BRAINROT_DB")
    or Path(__file__).resolve().parent.parent / "data" / "brainrot.db"
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS yt_source (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ext_id      TEXT,
    url         TEXT    NOT NULL,
    path        TEXT,
    title       TEXT    NOT NULL DEFAULT '',
    duration_s  REAL,
    recipe      TEXT    NOT NULL DEFAULT '',
    format_json TEXT,
    chapters_json TEXT,
    subs_path   TEXT,
    created_at  INTEGER NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'Downloaded'
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_yt_source_ext
    ON yt_source (ext_id) WHERE ext_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS yt_clip (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id  INTEGER NOT NULL REFERENCES yt_source(id) ON DELETE CASCADE,
    start_s    REAL    NOT NULL,
    end_s      REAL    NOT NULL,
    reason     TEXT    NOT NULL DEFAULT '',
    status     TEXT    NOT NULL DEFAULT 'Candidate',
    video_id   INTEGER,
    format_json TEXT,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_yt_clip_status ON yt_clip (status);
CREATE INDEX IF NOT EXISTS idx_yt_clip_source ON yt_clip (source_id);
"""

SOURCE_STATUSES = ("Downloaded", "Formatted", "Exhausted")
CLIP_STATUSES = ("Candidate", "Used", "Skipped")


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive migrations for DBs created by older versions."""
    source_cols = {row["name"] for row in conn.execute("PRAGMA table_info(yt_source)")}
    for name in ("chapters_json", "subs_path"):
        if name not in source_cols:
            conn.execute(f"ALTER TABLE yt_source ADD COLUMN {name} TEXT")
    clip_cols = {row["name"] for row in conn.execute("PRAGMA table_info(yt_clip)")}
    if "format_json" not in clip_cols:
        conn.execute("ALTER TABLE yt_clip ADD COLUMN format_json TEXT")
    conn.commit()


def _now() -> int:
    return int(time.time())


class Store:
    """Thin wrapper over the yt_* tables. One connection per instance."""

    def __init__(self, path: str | Path | None = None) -> None:
        p = Path(path) if path is not None else DEFAULT_DB
        p.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(p)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        _migrate(self.conn)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---- sources --------------------------------------------------------

    def add_source(self, url: str, *, ext_id=None, path=None, title="",
                   duration_s=None, recipe="", chapters=None, subs_path=None) -> int:
        """Insert (or update by ext_id) a source and return its id."""
        chapters_json = json.dumps(chapters, ensure_ascii=False) if chapters else None
        if ext_id:
            row = self.conn.execute("SELECT id FROM yt_source WHERE ext_id = ?",
                                    (str(ext_id),)).fetchone()
            if row:
                self.conn.execute(
                    "UPDATE yt_source SET url = ?, path = COALESCE(?, path), "
                    "title = COALESCE(NULLIF(?, ''), title), "
                    "duration_s = COALESCE(?, duration_s), "
                    "recipe = COALESCE(NULLIF(?, ''), recipe), "
                    "chapters_json = COALESCE(?, chapters_json), "
                    "subs_path = COALESCE(?, subs_path) WHERE id = ?",
                    (url, path, title, duration_s, recipe, chapters_json, subs_path,
                     row["id"]))
                self.conn.commit()
                return int(row["id"])
        cur = self.conn.execute(
            "INSERT INTO yt_source (ext_id, url, path, title, duration_s, recipe, "
            "chapters_json, subs_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(ext_id) if ext_id else None, url, path, title, duration_s, recipe,
             chapters_json, subs_path, _now()))
        self.conn.commit()
        return int(cur.lastrowid)

    def get_source(self, source_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM yt_source WHERE id = ?",
                                (int(source_id),)).fetchone()
        return dict(row) if row else None

    def list_sources(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT s.*, "
            "(SELECT COUNT(*) FROM yt_clip c WHERE c.source_id = s.id AND c.status = 'Candidate') AS candidates, "
            "(SELECT COUNT(*) FROM yt_clip c WHERE c.source_id = s.id AND c.status = 'Used') AS used "
            "FROM yt_source s ORDER BY s.id")]

    def set_source_status(self, source_id: int, status: str) -> None:
        if status not in SOURCE_STATUSES:
            raise ValueError(f"status must be one of {SOURCE_STATUSES}")
        self.conn.execute("UPDATE yt_source SET status = ? WHERE id = ?",
                          (status, int(source_id)))
        self.conn.commit()

    # ---- format (per video) ---------------------------------------------

    def set_format(self, source_id: int, spec) -> dict:
        """Store the vision-derived format (regions) for a source. Marks Formatted."""
        if self.get_source(source_id) is None:
            raise KeyError(f"source {source_id} not found")
        self.conn.execute(
            "UPDATE yt_source SET format_json = ?, status = 'Formatted' WHERE id = ?",
            (json.dumps(spec, ensure_ascii=False), int(source_id)))
        self.conn.commit()
        return dict(self.get_source(source_id))

    def get_format(self, source_id: int):
        row = self.conn.execute("SELECT format_json FROM yt_source WHERE id = ?",
                                (int(source_id),)).fetchone()
        if row is None or not row["format_json"]:
            return None
        return json.loads(row["format_json"])

    def get_chapters(self, source_id: int):
        row = self.conn.execute("SELECT chapters_json FROM yt_source WHERE id = ?",
                                (int(source_id),)).fetchone()
        if row is None or not row["chapters_json"]:
            return []
        return json.loads(row["chapters_json"])

    def get_subs_path(self, source_id: int):
        row = self.conn.execute("SELECT subs_path FROM yt_source WHERE id = ?",
                                (int(source_id),)).fetchone()
        return (row["subs_path"] if row else None) or None

    # ---- clips ----------------------------------------------------------

    def add_candidates(self, source_id: int, items) -> list[int]:
        """Insert candidate clip windows: ``[{'start', 'end', 'reason'}]``."""
        if self.get_source(source_id) is None:
            raise KeyError(f"source {source_id} not found")
        ids = []
        for item in items:
            start, end = float(item["start"]), float(item["end"])
            if end <= start:
                raise ValueError(f"clip end must be after start ({start}..{end})")
            cur = self.conn.execute(
                "INSERT INTO yt_clip (source_id, start_s, end_s, reason, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (int(source_id), start, end, str(item.get("reason", "")), _now()))
            ids.append(int(cur.lastrowid))
        self.conn.commit()
        return ids

    def list_clips(self, source_id=None, status=None) -> list[dict]:
        sql, args = "SELECT * FROM yt_clip", []
        where = []
        if source_id is not None:
            where.append("source_id = ?")
            args.append(int(source_id))
        if status is not None:
            where.append("status = ?")
            args.append(str(status))
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id"
        return [dict(r) for r in self.conn.execute(sql, args)]

    def get_clip(self, clip_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM yt_clip WHERE id = ?",
                                (int(clip_id),)).fetchone()
        return dict(row) if row else None

    # ---- per-clip format (hybrid: overrides the source format) ----------

    def set_clip_format(self, clip_id: int, spec) -> dict:
        """Store a per-clip layout (used when the clip's layout differs)."""
        if self.get_clip(clip_id) is None:
            raise KeyError(f"clip {clip_id} not found")
        self.conn.execute("UPDATE yt_clip SET format_json = ? WHERE id = ?",
                          (json.dumps(spec, ensure_ascii=False), int(clip_id)))
        self.conn.commit()
        return dict(self.get_clip(clip_id))

    def get_clip_format(self, clip_id: int):
        row = self.conn.execute("SELECT format_json FROM yt_clip WHERE id = ?",
                                (int(clip_id),)).fetchone()
        if row is None or not row["format_json"]:
            return None
        return json.loads(row["format_json"])

    def mark_clip(self, clip_id: int, status: str, video_id=None) -> dict:
        """Mark a clip Used/Skipped; exhausts the source when nothing is left."""
        if status not in CLIP_STATUSES:
            raise ValueError(f"status must be one of {CLIP_STATUSES}")
        clip = self.get_clip(clip_id)
        if clip is None:
            raise KeyError(f"clip {clip_id} not found")
        self.conn.execute("UPDATE yt_clip SET status = ?, video_id = COALESCE(?, video_id) "
                          "WHERE id = ?", (status, video_id, int(clip_id)))
        self.conn.commit()
        left = self.conn.execute(
            "SELECT COUNT(*) n FROM yt_clip WHERE source_id = ? AND status = 'Candidate'",
            (clip["source_id"],)).fetchone()["n"]
        if not left:
            self.set_source_status(clip["source_id"], "Exhausted")
        return dict(self.get_clip(clip_id))

    # ---- work queue -----------------------------------------------------

    def next_work(self) -> dict:
        """What to do next: format | clip | find | download."""
        row = self.conn.execute(
            "SELECT * FROM yt_source WHERE format_json IS NULL ORDER BY id LIMIT 1").fetchone()
        if row:
            return {"action": "format", "source": dict(row)}
        row = self.conn.execute(
            "SELECT * FROM yt_clip WHERE status = 'Candidate' ORDER BY id LIMIT 1").fetchone()
        if row:
            return {"action": "clip", "clip": dict(row),
                    "source": self.get_source(row["source_id"])}
        row = self.conn.execute(
            "SELECT * FROM yt_source WHERE status = 'Formatted' AND format_json IS NOT NULL "
            "ORDER BY id LIMIT 1").fetchone()
        if row:
            return {"action": "find", "source": dict(row)}
        return {"action": "download"}
