"""SQLite connection and schema for the long-term memory."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

# Default DB location: <project>/data/brainrot.db  (override with BRAINROT_DB).
DEFAULT_DB = Path(
    os.environ.get("BRAINROT_DB")
    or Path(__file__).resolve().parent.parent / "data" / "brainrot.db"
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS video (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    art         TEXT    NOT NULL,
    len_s       INTEGER NOT NULL,
    theme       TEXT    NOT NULL DEFAULT '',
    recipe      TEXT    NOT NULL DEFAULT '',
    created_at  INTEGER NOT NULL,
    upload_at   INTEGER,
    status      TEXT    NOT NULL DEFAULT 'Created'
);

CREATE TABLE IF NOT EXISTS metric (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL REFERENCES video(id) ON DELETE CASCADE,
    ts       INTEGER NOT NULL,
    views    INTEGER NOT NULL,
    comments INTEGER NOT NULL,
    likes    INTEGER NOT NULL,
    UNIQUE (video_id, ts)
);

CREATE INDEX IF NOT EXISTS idx_metric_video_ts ON metric (video_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_video_status    ON video (status);
CREATE INDEX IF NOT EXISTS idx_video_upload_at ON video (upload_at);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive migrations for DBs created by older schema versions."""
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(video)")}
    if "recipe" not in cols:
        conn.execute("ALTER TABLE video ADD COLUMN recipe TEXT NOT NULL DEFAULT ''")
    conn.commit()


def connect(path: str | os.PathLike | None = None) -> sqlite3.Connection:
    """Open a connection with sane defaults (FKs on, row access by name)."""
    path = Path(path) if path is not None else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(path: str | os.PathLike | None = None) -> sqlite3.Connection:
    """Open a connection and ensure the schema exists."""
    conn = connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    _migrate(conn)
    return conn
