"""SQLite storage. All queries are parameterised."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  acc TEXT PRIMARY KEY,
  pages INTEGER NOT NULL,
  has_text_layer INTEGER NOT NULL,
  text TEXT NOT NULL,
  title TEXT, doc_type TEXT, date TEXT, lang TEXT,
  refs_json TEXT, entities_json TEXT, summary TEXT,
  meta_source TEXT, text_source TEXT, injection_flag INTEGER DEFAULT 0,
  ingested_at REAL
);
CREATE TABLE IF NOT EXISTS pages (
  acc TEXT NOT NULL, page INTEGER NOT NULL, width INTEGER, height INTEGER,
  lines_json TEXT NOT NULL, source TEXT NOT NULL, model TEXT,
  PRIMARY KEY (acc, page)
);
CREATE TABLE IF NOT EXISTS chunks (
  id TEXT PRIMARY KEY, acc TEXT NOT NULL, page INTEGER NOT NULL,
  line_start INTEGER NOT NULL, line_end INTEGER NOT NULL,
  text TEXT NOT NULL, vector BLOB
);
CREATE INDEX IF NOT EXISTS chunks_acc ON chunks(acc);
CREATE TABLE IF NOT EXISTS investigations (
  step_id TEXT PRIMARY KEY, verdict_json TEXT NOT NULL, events_json TEXT NOT NULL,
  provider TEXT NOT NULL, model TEXT, created_at REAL NOT NULL, duration_s REAL
);
CREATE TABLE IF NOT EXISTS trials (
  id TEXT PRIMARY KEY, step_id TEXT NOT NULL, plan_json TEXT NOT NULL, status TEXT NOT NULL,
  evolus_execution_id TEXT, history_json TEXT NOT NULL, created_at REAL, updated_at REAL
);
CREATE TABLE IF NOT EXISTS change_events (
  id TEXT PRIMARY KEY, event_json TEXT NOT NULL, alerts_json TEXT NOT NULL, created_at REAL
);
CREATE TABLE IF NOT EXISTS metrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT, stage TEXT, role TEXT, model TEXT, provider TEXT,
  latency_ms REAL, tokens_in INTEGER, tokens_out INTEGER, ok INTEGER, ts REAL
);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS evolus_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT, endpoint TEXT, status INTEGER, credits REAL, ts REAL, note TEXT
);
"""

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None
_conn_path: Path | None = None


def connect() -> sqlite3.Connection:
    global _conn, _conn_path
    path = config.settings.db_path
    with _lock:
        if _conn is None or _conn_path != path:
            path.parent.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.execute("PRAGMA foreign_keys=ON")
            _conn.executescript(SCHEMA)
            _conn_path = path
        return _conn


def close() -> None:
    global _conn, _conn_path
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn, _conn_path = None, None


@contextmanager
def tx():
    c = connect()
    with _lock:
        c.execute("BEGIN")
        try:
            yield c
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise


def q(sql: str, params: tuple | list = ()) -> list[sqlite3.Row]:
    with _lock:
        return connect().execute(sql, params).fetchall()


def q1(sql: str, params: tuple | list = ()) -> sqlite3.Row | None:
    with _lock:
        return connect().execute(sql, params).fetchone()


def ex(sql: str, params: tuple | list = ()) -> None:
    with _lock:
        connect().execute(sql, params)


def kv_get(k: str, default=None):
    r = q1("SELECT v FROM kv WHERE k=?", (k,))
    return json.loads(r["v"]) if r else default


def kv_set(k: str, v) -> None:
    ex("INSERT INTO kv(k, v) VALUES(?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, json.dumps(v)))


def record_metric(stage: str, role: str, model: str, provider: str, latency_ms: float, tokens_in: int = 0,
                  tokens_out: int = 0, ok: bool = True) -> None:
    ex("INSERT INTO metrics(stage, role, model, provider, latency_ms, tokens_in, tokens_out, ok, ts) VALUES(?,?,?,?,?,?,?,?,?)",
       (stage, role, model, provider, latency_ms, tokens_in, tokens_out, int(ok), time.time()))
