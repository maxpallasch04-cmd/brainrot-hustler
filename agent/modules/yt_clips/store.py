"""SQLite state for the YT-clip art: source videos + candidate clips.

Shares the project DB (``data/brainrot.db`` / ``BRAINROT_DB``) with
``longterm_memory`` but owns its own tables: ``yt_source``, ``yt_clip``.

State machine
-------------
``yt_source.status``:  Downloaded (work: find candidates)
                       Exhausted  (nothing left to clip)
``yt_clip.status``:    Candidate  -> Used | Skipped

The layout does not live here. It is an ``editor`` recipe file; this store only
knows sources, candidate windows and their status.
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
    boxes_json  TEXT,
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
    segments_json TEXT,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_yt_clip_status ON yt_clip (status);
CREATE INDEX IF NOT EXISTS idx_yt_clip_source ON yt_clip (source_id);
"""

SOURCE_STATUSES = ("Downloaded", "Exhausted")
CLIP_STATUSES = ("Candidate", "Used", "Skipped")


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive migrations for DBs created by older versions."""
    source_cols = {row["name"] for row in conn.execute("PRAGMA table_info(yt_source)")}
    for name in ("chapters_json", "subs_path", "boxes_json"):
        if name not in source_cols:
            conn.execute(f"ALTER TABLE yt_source ADD COLUMN {name} TEXT")
    clip_cols = {row["name"] for row in conn.execute("PRAGMA table_info(yt_clip)")}
    if "segments_json" not in clip_cols:
        conn.execute("ALTER TABLE yt_clip ADD COLUMN segments_json TEXT")
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
        if row is None:
            return None
        out = dict(row)
        out["boxes"] = json.loads(out["boxes_json"]) if out.get("boxes_json") else None
        return out

    def list_sources(self, recipe: str | None = None) -> list[dict]:
        sql = (
            "SELECT s.*, "
            "(SELECT COUNT(*) FROM yt_clip c WHERE c.source_id = s.id AND c.status = 'Candidate') AS candidates, "
            "(SELECT COUNT(*) FROM yt_clip c WHERE c.source_id = s.id AND c.status = 'Used') AS used "
            "FROM yt_source s"
        )
        args: list = []
        if recipe:
            sql += " WHERE s.recipe = ?"
            args.append(str(recipe))
        sql += " ORDER BY s.id"
        return [dict(r) for r in self.conn.execute(sql, args)]

    def set_source_status(self, source_id: int, status: str) -> None:
        if status not in SOURCE_STATUSES:
            raise ValueError(f"status must be one of {SOURCE_STATUSES}")
        self.conn.execute("UPDATE yt_source SET status = ? WHERE id = ?",
                          (status, int(source_id)))
        self.conn.commit()

    def set_recipe(self, source_id: int, recipe: str) -> dict:
        """Tag a downloaded video with the recipe that picked it."""
        name = str(recipe or "").strip()
        if not name:
            raise ValueError("recipe name must not be empty")
        if self.get_source(source_id) is None:
            raise KeyError(f"source {source_id} not found")
        self.conn.execute("UPDATE yt_source SET recipe = ? WHERE id = ?",
                          (name, int(source_id)))
        self.conn.commit()
        return dict(self.get_source(source_id))

    # ---- boxes (per video, measured once) -------------------------------

    def set_boxes(self, source_id: int, boxes) -> dict:
        """Store the measured sub-boxes of a source: ``{name: [x, y, w, h]}``.

        Canonical per video (``boxes.score`` etc.). Recipes copy what they need;
        ``ocr`` never reads this — it takes ``--box`` explicitly.
        """
        if not isinstance(boxes, dict) or not boxes:
            raise ValueError("boxes must be a non-empty object {name: [x,y,w,h]}")
        clean = {}
        for name, value in boxes.items():
            if not isinstance(value, (list, tuple)) or len(value) != 4:
                raise ValueError(f"box {name!r} must be [x, y, w, h]")
            try:
                x, y, w, h = (int(float(v)) for v in value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"box {name!r} values must be numbers") from exc
            if w <= 0 or h <= 0:
                raise ValueError(f"box {name!r} width/height must be positive")
            clean[str(name)] = [x, y, w, h]
        if self.get_source(source_id) is None:
            raise KeyError(f"source {source_id} not found")
        self.conn.execute("UPDATE yt_source SET boxes_json = ? WHERE id = ?",
                          (json.dumps(clean, ensure_ascii=False), int(source_id)))
        self.conn.commit()
        return dict(self.get_source(source_id))

    def get_boxes(self, source_id: int):
        row = self.conn.execute("SELECT boxes_json FROM yt_source WHERE id = ?",
                                (int(source_id),)).fetchone()
        if row is None or not row["boxes_json"]:
            return None
        return json.loads(row["boxes_json"])

    # ---- clips ----------------------------------------------------------

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
        """Insert candidates: ``[{'start', 'end', 'reason'}]`` or a ``segments`` list.

        ``segments`` (two windows that get concatenated, e.g. trick + score) are
        stored verbatim; the row's ``start_s``/``end_s`` span the whole composite
        so the existing queue/list logic keeps working.
        """
        if self.get_source(source_id) is None:
            raise KeyError(f"source {source_id} not found")
        ids = []
        for item in items:
            segments = item.get("segments")
            if segments:
                segs = []
                for seg in segments:
                    s, e = float(seg["start"]), float(seg["end"])
                    if e <= s:
                        raise ValueError(f"segment end must be after start ({s}..{e})")
                    row = {"start": s, "end": e}
                    if seg.get("reason") is not None:
                        row["reason"] = seg["reason"]
                    segs.append(row)
                start, end = min(s["start"] for s in segs), max(s["end"] for s in segs)
                segments_json = json.dumps(segs, ensure_ascii=False)
            else:
                start, end = float(item["start"]), float(item["end"])
                if end <= start:
                    raise ValueError(f"clip end must be after start ({start}..{end})")
                segments_json = None
            cur = self.conn.execute(
                "INSERT INTO yt_clip (source_id, start_s, end_s, reason, segments_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (int(source_id), start, end, str(item.get("reason", "")),
                 segments_json, _now()))
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

    # ---- per-clip status -----------------------------------------------

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

    def next_work(self, recipe: str) -> dict:
        """What to do next **for one recipe**: clip | find | download.

        The recipe is the queue key: sources of other recipes are invisible here,
        so switching from one art to another does not keep surfacing old work.
        """
        name = str(recipe or "").strip()
        if not name:
            raise ValueError("next_work needs a recipe name")

        row = self.conn.execute(
            "SELECT c.* FROM yt_clip c JOIN yt_source s ON s.id = c.source_id "
            "WHERE c.status = 'Candidate' AND s.recipe = ? ORDER BY c.id LIMIT 1",
            (name,)).fetchone()
        if row:
            return {"action": "clip", "recipe": name, "clip": dict(row),
                    "source": self.get_source(row["source_id"])}

        row = self.conn.execute(
            "SELECT * FROM yt_source s WHERE s.status != 'Exhausted' AND s.recipe = ? "
            "AND NOT EXISTS (SELECT 1 FROM yt_clip c WHERE c.source_id = s.id) "
            "ORDER BY s.id LIMIT 1", (name,)).fetchone()
        if row:
            return {"action": "find", "recipe": name, "source": self.get_source(row["id"])}

        return {"action": "download", "recipe": name}
