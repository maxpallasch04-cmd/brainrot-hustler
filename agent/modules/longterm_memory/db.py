"""SQLite connection and schema for the long-term memory.

The `video` table is the single source of truth for the content plan:
one row per video, from `planned` (idea + recipe + upload time) through
`generated` (file on disk) to `uploaded`.

Default DB location: <workspace>/memory/brainrot.db (override with BRAINROT_DB).
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

# <workspace>/modules/longterm_memory/db.py -> <workspace>/memory/brainrot.db
WORKSPACE = Path(__file__).resolve().parent.parent.parent

DEFAULT_DB = Path(
    os.environ.get("BRAINROT_DB")
    or WORKSPACE / "memory" / "brainrot.db"
)

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS video (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    idea        TEXT    NOT NULL DEFAULT '',
    title       TEXT    NOT NULL DEFAULT '',
    description TEXT    NOT NULL DEFAULT '',
    art         TEXT    NOT NULL DEFAULT 'YT-Clip',
    recipe      TEXT    NOT NULL DEFAULT '',
    theme       TEXT    NOT NULL DEFAULT '',
    file        TEXT,
    len_s       INTEGER NOT NULL DEFAULT 0,
    plan_at     INTEGER,
    created_at  INTEGER NOT NULL,
    upload_at   INTEGER,
    status      TEXT    NOT NULL DEFAULT 'planned'
);
"""

# Columns added after v1 (older DBs get them via ALTER TABLE).
_ADDED_COLUMNS = {
    "idea": "TEXT NOT NULL DEFAULT ''",
    "file": "TEXT",
    "plan_at": "INTEGER",
}

_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_video_status  ON video (status);
CREATE INDEX IF NOT EXISTS idx_video_plan_at ON video (plan_at);
"""

# v1 status names -> v2
_STATUS_MAP = {"Created": "generated", "Uploaded": "uploaded"}


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive, non-destructive migration from the v1 schema."""
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(video)")}
    for name, decl in _ADDED_COLUMNS.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE video ADD COLUMN {name} {decl}")
    for old, new in _STATUS_MAP.items():
        conn.execute("UPDATE video SET status = ? WHERE status = ?", (new, old))
    # v1 kept metrics; the plan does not use them (re-add when needed).
    conn.execute("DROP TABLE IF EXISTS metric")
    conn.executescript(_INDEXES)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
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
