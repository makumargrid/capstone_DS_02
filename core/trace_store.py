"""
core/trace_store.py — Structured SQLite trace store for pipeline observability.

Every run and its stages are recorded as queryable rows. The flat per-run
JSON artifact files (01_design_brief.json, etc.) are kept as the by-reference
payload — the trace store indexes and relates them.

Schema:
  runs     — one row per pipeline invocation
  stages   — one row per stage (intent, plan, compile, inspect, review, handoff)
  artifacts — file artifacts produced per stage

CALLED BY: pipeline.py (at each stage boundary).
"""
from __future__ import annotations
import sqlite3
import json
import os
import hashlib
import datetime


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()[:16]


class TraceStore:
    """SQLite-backed trace store for pipeline runs."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._init_schema()
        return self._conn

    def _init_schema(self):
        conn = self._conn
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                prompt TEXT,
                process TEXT,
                started_at TEXT,
                completed_at TEXT,
                verdict TEXT,
                custom_used INTEGER DEFAULT 0,
                requires_review INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS stages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT REFERENCES runs(run_id),
                stage TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'started',
                started_at TEXT,
                completed_at TEXT,
                input_hash TEXT,
                output_hash TEXT,
                error TEXT,
                metrics TEXT
            );

            CREATE TABLE IF NOT EXISTS artifacts (
                run_id TEXT REFERENCES runs(run_id),
                stage TEXT,
                filename TEXT,
                path TEXT
            );
        """)
        conn.commit()

    def start_run(self, run_id: str, prompt: str, process: str = "FDM") -> str:
        conn = self._connect()
        now = datetime.datetime.now().isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO runs(run_id, prompt, process, started_at) VALUES (?,?,?,?)",
            (run_id, prompt[:500], process, now),
        )
        conn.commit()
        return run_id

    def log_stage(self, run_id: str, stage: str, status: str,
                  input_data: dict | None = None, output_data: dict | None = None,
                  error: str | None = None, metrics: dict | None = None):
        conn = self._connect()
        now = datetime.datetime.now().isoformat()
        in_hash = _sha256(json.dumps(input_data, sort_keys=True, default=str)) if input_data else None
        out_hash = _sha256(json.dumps(output_data, sort_keys=True, default=str)) if output_data else None

        # Check if this stage already has a row for this run
        existing = conn.execute(
            "SELECT id FROM stages WHERE run_id=? AND stage=? AND status='started'",
            (run_id, stage)
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE stages SET status=?, completed_at=?, input_hash=?, output_hash=?,
                   error=?, metrics=? WHERE id=?""",
                (status, now, in_hash, out_hash, error, json.dumps(metrics) if metrics else None,
                 existing["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO stages(run_id, stage, status, started_at, completed_at,
                   input_hash, output_hash, error, metrics)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (run_id, stage, status, now, now, in_hash, out_hash, error,
                 json.dumps(metrics) if metrics else None),
            )
        conn.commit()

    def record_artifact(self, run_id: str, stage: str, filename: str, path: str):
        conn = self._connect()
        conn.execute(
            "INSERT INTO artifacts(run_id, stage, filename, path) VALUES (?,?,?,?)",
            (run_id, stage, filename, path),
        )
        conn.commit()

    def complete_run(self, run_id: str, verdict: str, custom_used: bool = False,
                     requires_review: bool = False):
        conn = self._connect()
        now = datetime.datetime.now().isoformat()
        conn.execute(
            "UPDATE runs SET completed_at=?, verdict=?, custom_used=?, requires_review=? WHERE run_id=?",
            (now, verdict, int(custom_used), int(requires_review), run_id),
        )
        conn.commit()

    def query_runs(self, where: str = "", params: tuple = ()) -> list[dict]:
        """Return all matching runs as dicts."""
        conn = self._connect()
        sql = "SELECT * FROM runs"
        if where:
            sql += f" WHERE {where}"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def query_stages(self, run_id: str) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM stages WHERE run_id=? ORDER BY id", (run_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None