"""SQLite connection, schema and channel profiles.

The ``video`` table is the single source of truth for the content plan:
one row per video, from `planned` (idea + recipe + upload time) through
`generated` (file on disk) to `uploaded`.

The ``channel`` table holds everything that is specific to one channel
(niche, recipes, upload tempo, quiet hours, format, storage prefix).

Default DB location: <workspace>/memory/brainrot.db (override with BRAINROT_DB).
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

import brainrot_paths as paths

# <workspace>/modules/longterm_memory/db.py -> <workspace>/memory/brainrot.db
WORKSPACE = paths.WORKSPACE

DEFAULT_DB = Path(os.environ.get("BRAINROT_DB") or paths.db_path())

SCHEMA_VERSION = 3

SCHEMA = """
CREATE TABLE IF NOT EXISTS channel (
    id          TEXT    PRIMARY KEY,
    niche       TEXT    NOT NULL DEFAULT '',
    art         TEXT    NOT NULL DEFAULT 'YT-Clip',
    recipes     TEXT    NOT NULL DEFAULT '[]',
    open_target INTEGER NOT NULL DEFAULT 2,
    lead_h      REAL    NOT NULL DEFAULT 4,
    quiet_start TEXT    NOT NULL DEFAULT '22:00',
    quiet_end   TEXT    NOT NULL DEFAULT '10:00',
    tz          TEXT    NOT NULL DEFAULT 'Europe/Berlin',
    format      TEXT    NOT NULL DEFAULT '9:16,1280',
    r2_prefix   TEXT    NOT NULL DEFAULT '',
    recipients  TEXT    NOT NULL DEFAULT '[]',
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS video (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id  TEXT    NOT NULL DEFAULT '',
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

# Columns added after earlier versions (older DBs get them via ALTER TABLE).
_ADDED_COLUMNS = {
    "idea": "TEXT NOT NULL DEFAULT ''",
    "file": "TEXT",
    "plan_at": "INTEGER",
    "channel_id": "TEXT NOT NULL DEFAULT ''",
}

_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_video_channel   ON video (channel_id, status);
CREATE INDEX IF NOT EXISTS idx_video_status    ON video (status);
CREATE INDEX IF NOT EXISTS idx_video_plan_at   ON video (plan_at);
"""

# v1 status names -> v2
_STATUS_MAP = {"Created": "generated", "Uploaded": "uploaded"}

PROFILE_DEFAULTS = {
    "niche": "",
    "art": "YT-Clip",
    "recipes": [],
    "open_target": 2,
    "lead_h": 4.0,
    "quiet_start": "22:00",
    "quiet_end": "10:00",
    "tz": "Europe/Berlin",
    "format": "9:16,1280",
    "r2_prefix": "",
    "recipients": [],
    "active": 1,
}

JSON_FIELDS = ("recipes", "recipients")


class ChannelError(RuntimeError):
    """Unbekannter oder fehlender Kanal."""


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive, non-destructive migrations from older schemas."""
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(video)")}
    for name, decl in _ADDED_COLUMNS.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE video ADD COLUMN {name} {decl}")
    for old, new in _STATUS_MAP.items():
        conn.execute("UPDATE video SET status = ? WHERE status = ?", (new, old))
    # v1 kept metrics; the plan does not use them (re-add when needed).
    conn.execute("DROP TABLE IF EXISTS metric")

    # Alt-Daten ohne Kanal: genau ein Kanal -> dorthin zuordnen.
    rows = conn.execute("SELECT id FROM channel").fetchall()
    if len(rows) == 1:
        only = rows[0]["id"]
        conn.execute("UPDATE video SET channel_id = ? WHERE channel_id = ''", (only,))
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(yt_source)")}
        if "channel_id" in cols:
            conn.execute("UPDATE yt_source SET channel_id = ? WHERE channel_id = ''", (only,))

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


# ---- channel profiles ---------------------------------------------------


def _decode(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    out = dict(row)
    for name in JSON_FIELDS:
        raw = out.get(name)
        try:
            out[name] = json.loads(raw) if raw else []
        except (TypeError, ValueError):
            out[name] = []
    return out


def get_channel(conn: sqlite3.Connection, channel_id: str) -> dict | None:
    """Profile of one channel, JSON fields decoded. ``None`` if unknown."""
    return _decode(conn.execute(
        "SELECT * FROM channel WHERE id = ?", (str(channel_id),)).fetchone())


def require_channel(conn: sqlite3.Connection, channel_id: str) -> dict:
    """Like :func:`get_channel`, but raises for unknown channels."""
    profile = get_channel(conn, channel_id)
    if profile is None:
        raise ChannelError(
            f"unbekannter Kanal {channel_id!r} - anlegen mit "
            f"`longterm_memory.cli channel-set --channel {channel_id} ...`"
        )
    return profile


def list_channels(conn: sqlite3.Connection) -> list[dict]:
    return [_decode(r) for r in conn.execute("SELECT * FROM channel ORDER BY id")]


def upsert_channel(conn: sqlite3.Connection, channel_id: str, **fields) -> dict:
    """Create or update a channel profile; unknown keys are rejected."""
    channel_id = str(channel_id).strip().lower()
    if not paths.CHANNEL_PATTERN.match(channel_id):
        raise ValueError(f"invalid channel id {channel_id!r}")
    unknown = set(fields) - set(PROFILE_DEFAULTS)
    if unknown:
        raise ValueError(f"unknown profile fields: {sorted(unknown)}")

    values = dict(PROFILE_DEFAULTS)
    values["r2_prefix"] = f"brainrot/{channel_id}/"
    existing = get_channel(conn, channel_id)
    if existing:
        for name in PROFILE_DEFAULTS:
            values[name] = existing[name]
        values["r2_prefix"] = existing["r2_prefix"]
    values.update(fields)

    for name in JSON_FIELDS:
        values[name] = json.dumps(values[name], ensure_ascii=False)

    now = int(time.time())
    if existing:
        sets = ", ".join(f"{name} = ?" for name in values)
        conn.execute(
            f"UPDATE channel SET {sets}, updated_at = ? WHERE id = ?",
            (*values.values(), now, channel_id),
        )
    else:
        now = int(time.time())
        cols = ["id", *values.keys(), "created_at", "updated_at"]
        marks = ", ".join("?" for _ in cols)
        conn.execute(
            f"INSERT INTO channel ({', '.join(cols)}) VALUES ({marks})",
            (channel_id, *values.values(), now, now),
        )
    conn.commit()

    # Erster Kanal übernimmt Alt-Daten, die noch keinen Kanal haben.
    count = conn.execute("SELECT COUNT(*) AS n FROM channel").fetchone()["n"]
    if count == 1:
        conn.execute("UPDATE video SET channel_id = ? WHERE channel_id = ''",
                     (channel_id,))
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(yt_source)")}
        if "channel_id" in cols:
            conn.execute("UPDATE yt_source SET channel_id = ? WHERE channel_id = ''",
                         (channel_id,))
        conn.commit()

    return require_channel(conn, channel_id)
