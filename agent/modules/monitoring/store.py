"""Persistence for content-analysis reports.

Reports live in the same SQLite database as the long-term memory (a `report`
table), so the analysis is one durable log. The payload is stored as JSON so the
report shape can evolve without schema churn.
"""

from __future__ import annotations

import json

from longterm_memory import db

SCHEMA = """
CREATE TABLE IF NOT EXISTS report (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      INTEGER NOT NULL,
    payload TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_report_ts ON report (ts);
"""


class ReportStore:
    """Append-only log of content-analysis reports."""

    def __init__(self, path=None) -> None:
        self.conn = db.init_db(path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "ReportStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def append(self, report: dict) -> None:
        """Store one report (JSON payload)."""
        self.conn.execute("INSERT INTO report (ts, payload) VALUES (?, ?)",
                          (int(report["ts"]), json.dumps(report, ensure_ascii=False)))
        self.conn.commit()

    def recent(self, n: int = 2) -> list[dict]:
        """The last `n` reports, oldest first."""
        rows = self.conn.execute(
            "SELECT payload FROM report ORDER BY ts DESC, id DESC LIMIT ?", (int(n),)
        ).fetchall()
        return [json.loads(r["payload"]) for r in reversed(rows)]

    def all(self) -> list[dict]:
        rows = self.conn.execute("SELECT payload FROM report ORDER BY ts, id").fetchall()
        return [json.loads(r["payload"]) for r in rows]
