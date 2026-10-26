"""SQLite storage for settings, history, jobs and events."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS recognition_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    mode TEXT NOT NULL,
    sign_label TEXT,
    sign_confidence REAL,
    lip_label TEXT,
    lip_confidence REAL,
    final_label TEXT NOT NULL,
    accepted INTEGER NOT NULL,
    reason TEXT NOT NULL,
    latency_ms REAL
);
CREATE INDEX IF NOT EXISTS idx_history_ts ON recognition_history(ts);
CREATE TABLE IF NOT EXISTS training_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    modality TEXT NOT NULL,
    dataset TEXT NOT NULL,
    status TEXT NOT NULL,
    config TEXT,
    progress REAL DEFAULT 0,
    current_epoch INTEGER DEFAULT 0,
    total_epochs INTEGER DEFAULT 0,
    metrics TEXT,
    error TEXT,
    logs TEXT DEFAULT '[]'
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str | Path):
        self._path = str(path)
        self._lock = threading.Lock()
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self._path, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    # ---- settings ----

    def get_setting(self, key: str) -> Any | None:
        with self._lock, self._conn() as c:
            row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else None

    def set_setting(self, key: str, value: Any) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value)),
            )

    # ---- history ----

    def add_history(self, ev: dict[str, Any]) -> int:
        with self._lock, self._conn() as c:
            cur = c.execute(
                "INSERT INTO recognition_history"
                "(ts,mode,sign_label,sign_confidence,lip_label,lip_confidence,"
                "final_label,accepted,reason,latency_ms) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    ev.get("timestamp") or _now(),
                    ev["mode"],
                    ev.get("sign_label"),
                    ev.get("sign_confidence"),
                    ev.get("lip_label"),
                    ev.get("lip_confidence"),
                    ev["final_label"],
                    1 if ev.get("accepted") else 0,
                    ev.get("reason", ""),
                    ev.get("latency_ms"),
                ),
            )
            return cur.lastrowid or 0

    def list_history(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT * FROM recognition_history ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]

    def count_history(self) -> int:
        with self._lock, self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM recognition_history").fetchone()[0]

    def clear_history(self) -> int:
        with self._lock, self._conn() as c:
            cur = c.execute("DELETE FROM recognition_history")
            return cur.rowcount

    def prune_history(self, retention_days: int, max_entries: int) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM recognition_history WHERE ts < ?", (cutoff,))
            overflow = c.execute(
                "SELECT COUNT(*) FROM recognition_history"
            ).fetchone()[0] - max_entries
            if overflow > 0:
                c.execute(
                    "DELETE FROM recognition_history WHERE id IN "
                    "(SELECT id FROM recognition_history ORDER BY id ASC LIMIT ?)",
                    (overflow,),
                )
                return overflow
        return 0

    # ---- training jobs ----

    def create_job(self, modality: str, dataset: str, config: dict[str, Any]) -> int:
        with self._lock, self._conn() as c:
            cur = c.execute(
                "INSERT INTO training_jobs(created_at,modality,dataset,status,config) "
                "VALUES(?,?,?,?,?)",
                (_now(), modality, dataset, "QUEUED", json.dumps(config)),
            )
            return cur.lastrowid or 0

    def update_job(self, job_id: int, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields)
        with self._lock, self._conn() as c:
            c.execute(f"UPDATE training_jobs SET {cols} WHERE id=?", (*fields.values(), job_id))

    def get_job(self, job_id: int) -> dict[str, Any] | None:
        with self._lock, self._conn() as c:
            row = c.execute("SELECT * FROM training_jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def list_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT * FROM training_jobs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def append_job_log(self, job_id: int, line: str) -> None:
        with self._lock, self._conn() as c:
            row = c.execute("SELECT logs FROM training_jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                return
            logs = json.loads(row["logs"])
            logs.append({"ts": _now(), "line": line})
            c.execute(
                "UPDATE training_jobs SET logs=? WHERE id=?",
                (json.dumps(logs[-500:]), job_id),
            )
