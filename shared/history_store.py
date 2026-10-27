"""Persistent job history and analytics store for Still Loading...

Phase 13 records completed and failed jobs in a lightweight SQLite database,
enabling historical queries, failure analytics, and build duration metrics
across receiver restarts.
"""

from __future__ import annotations

import datetime
import json
import os
import sqlite3
import threading
from typing import Any

DEFAULT_DB_PATH = os.environ.get(
    "STILL_LOADING_DB",
    os.path.expanduser("~/.still_loading_history.db"),
)


def _parse_timestamp(ts: Any) -> float:
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str):
        try:
            clean = ts.replace("Z", "+00:00")
            return datetime.datetime.fromisoformat(clean).timestamp()
        except Exception:
            return 0.0
    return 0.0


class HistoryStore:
    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_history (
                    job_id TEXT PRIMARY KEY,
                    event TEXT NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL NOT NULL,
                    duration_seconds REAL NOT NULL,
                    progress INTEGER NOT NULL,
                    exit_code INTEGER,
                    is_failure INTEGER NOT NULL,
                    message TEXT,
                    category TEXT,
                    summary TEXT,
                    suggestion TEXT,
                    excerpt TEXT,
                    accepted_count INTEGER NOT NULL,
                    highest_sequence INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_job_end_time ON job_history(end_time DESC);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_job_failure ON job_history(is_failure);"
            )
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(job_history)").fetchall()
            }
            if "explanation_json" not in columns:
                conn.execute("ALTER TABLE job_history ADD COLUMN explanation_json TEXT")

    def record_job(self, events: list[dict], snapshot: dict[str, Any]) -> bool:
        """Record a completed or failed job into the persistent history table."""
        if not events or not snapshot:
            return False

        latest = snapshot.get("latest", events[-1])
        event_name = latest.get("event")
        if event_name not in ("completed", "failed"):
            return False

        job_id = snapshot["job_id"]
        start_ts = _parse_timestamp(events[0].get("timestamp", latest.get("timestamp", 0.0)))
        end_ts = _parse_timestamp(latest.get("timestamp", start_ts))
        duration = latest.get("elapsed_seconds")
        if duration is None:
            duration = max(0.0, end_ts - start_ts)
        else:
            duration = float(duration)

        progress = int(latest.get("progress", 0))
        exit_code = latest.get("exit_code")
        is_failure = 1 if latest.get("is_failure") else 0
        message = latest.get("message")

        explanation = snapshot.get("explanation") or latest.get("explanation") or {}
        if not isinstance(explanation, dict):
            explanation = {}
        category = explanation.get("category")
        summary = explanation.get("summary")
        suggestion = explanation.get("suggestion")
        explanation_json = json.dumps(explanation) if explanation else None

        excerpt = snapshot.get("excerpt") or latest.get("excerpt")
        accepted_count = int(snapshot.get("accepted_count", len(events)))
        highest_sequence = int(snapshot.get("highest_sequence", latest.get("sequence", 0)))
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO job_history (
                    job_id, event, start_time, end_time, duration_seconds,
                    progress, exit_code, is_failure, message, category,
                    summary, suggestion, excerpt, accepted_count,
                    highest_sequence, created_at, explanation_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    event_name,
                    start_ts,
                    end_ts,
                    float(duration),
                    progress,
                    exit_code,
                    is_failure,
                    message,
                    category,
                    summary,
                    suggestion,
                    excerpt,
                    accepted_count,
                    highest_sequence,
                    created_at,
                    explanation_json,
                ),
            )
        return True

    def list_jobs(
        self,
        limit: int = 50,
        offset: int = 0,
        failed_only: bool = False,
    ) -> list[dict[str, Any]]:
        """List historical jobs ordered by end_time descending."""
        query = "SELECT * FROM job_history"
        params: list[Any] = []

        if failed_only:
            query += " WHERE is_failure = 1"

        query += " ORDER BY end_time DESC LIMIT ? OFFSET ?"
        params.extend([max(1, min(200, limit)), max(0, offset)])

        with self._lock, self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            results = []
            for r in rows:
                row_dict = dict(r)
                row_dict["is_failure"] = bool(row_dict["is_failure"])
                stored = row_dict.get("explanation_json")
                parsed = None
                if isinstance(stored, str) and stored:
                    try:
                        loaded = json.loads(stored)
                    except json.JSONDecodeError:
                        loaded = None
                    if isinstance(loaded, dict):
                        parsed = loaded
                if parsed is not None:
                    row_dict["explanation"] = parsed
                elif row_dict["category"] or row_dict["summary"] or row_dict["suggestion"]:
                    row_dict["explanation"] = {
                        "category": row_dict["category"],
                        "summary": row_dict["summary"],
                        "suggestion": row_dict["suggestion"],
                    }
                else:
                    row_dict["explanation"] = None
                results.append(row_dict)
            return results

    def get_stats(self) -> dict[str, Any]:
        """Compute aggregate job analytics across all recorded runs."""
        with self._lock, self._get_connection() as conn:
            total_row = conn.execute(
                """
                SELECT 
                    COUNT(*) as total_jobs,
                    SUM(CASE WHEN is_failure = 0 THEN 1 ELSE 0 END) as completed_count,
                    SUM(CASE WHEN is_failure = 1 THEN 1 ELSE 0 END) as failed_count,
                    AVG(duration_seconds) as avg_duration,
                    SUM(duration_seconds) as total_duration
                FROM job_history
                """
            ).fetchone()

            cat_rows = conn.execute(
                """
                SELECT category, COUNT(*) as count 
                FROM job_history 
                WHERE is_failure = 1 AND category IS NOT NULL 
                GROUP BY category 
                ORDER BY count DESC
                """
            ).fetchall()

            total_jobs = total_row["total_jobs"] or 0
            completed_count = total_row["completed_count"] or 0
            failed_count = total_row["failed_count"] or 0
            avg_duration = round(total_row["avg_duration"] or 0.0, 2)
            total_duration = round(total_row["total_duration"] or 0.0, 2)
            success_rate = round((completed_count / total_jobs * 100.0), 1) if total_jobs > 0 else 0.0

            categories = {row["category"]: row["count"] for row in cat_rows}

            return {
                "total_jobs": total_jobs,
                "completed_count": completed_count,
                "failed_count": failed_count,
                "success_rate": success_rate,
                "avg_duration_seconds": avg_duration,
                "total_duration_seconds": total_duration,
                "failure_categories": categories,
            }

    def clear(self) -> None:
        """Clear all historical job entries (used primarily in tests)."""
        with self._lock, self._get_connection() as conn:
            conn.execute("DELETE FROM job_history")


# Global default store instance
_default_store: HistoryStore | None = None
_store_lock = threading.Lock()


def get_history_store() -> HistoryStore:
    global _default_store
    with _store_lock:
        if _default_store is None:
            _default_store = HistoryStore()
        return _default_store
