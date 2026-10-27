"""Unit tests for shared/history_store.py and GET /v1/history HTTP API."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "mac-agent"))

from history_store import HistoryStore
from http_api import build_server


class HistoryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_file.close()
        self.store = HistoryStore(db_path=self.temp_file.name)

    def tearDown(self) -> None:
        import os
        try:
            os.remove(self.temp_file.name)
        except OSError:
            pass

    def test_record_completed_and_failed_jobs(self) -> None:
        # 1. Completed job
        comp_events = [
            {"event": "started", "job_id": "job-c1", "sequence": 1, "timestamp": 1000.0, "progress": 0},
            {"event": "completed", "job_id": "job-c1", "sequence": 2, "timestamp": 1015.0, "elapsed_seconds": 15.0, "progress": 100, "exit_code": 0, "is_failure": False},
        ]
        comp_snap = {
            "job_id": "job-c1",
            "accepted_count": 2,
            "highest_sequence": 2,
            "latest": comp_events[-1],
        }
        self.assertTrue(self.store.record_job(comp_events, comp_snap))

        # 2. Failed job
        fail_events = [
            {"event": "started", "job_id": "job-f1", "sequence": 1, "timestamp": 2000.0, "progress": 0},
            {"event": "failed", "job_id": "job-f1", "sequence": 2, "timestamp": 2008.0, "elapsed_seconds": 8.0, "progress": 40, "exit_code": 1, "is_failure": True, "message": "Command failed"},
        ]
        fail_snap = {
            "job_id": "job-f1",
            "accepted_count": 2,
            "highest_sequence": 2,
            "latest": fail_events[-1],
            "excerpt": "ModuleNotFoundError: No module named 'numpy'",
            "explanation": {
                "category": "missing_dependency",
                "summary": "Missing Python module: 'numpy'",
                "suggestion": "pip install numpy",
            },
        }
        self.assertTrue(self.store.record_job(fail_events, fail_snap))

        # 3. List jobs
        jobs = self.store.list_jobs(limit=10)
        self.assertEqual(len(jobs), 2)
        # Ordered by end_time desc
        self.assertEqual(jobs[0]["job_id"], "job-f1")
        self.assertTrue(jobs[0]["is_failure"])
        self.assertEqual(jobs[0]["category"], "missing_dependency")
        self.assertIsNotNone(jobs[0]["explanation"])
        self.assertEqual(jobs[0]["explanation"]["suggestion"], "pip install numpy")

        self.assertEqual(jobs[1]["job_id"], "job-c1")
        self.assertFalse(jobs[1]["is_failure"])

        # 4. Filter failed only
        failed_jobs = self.store.list_jobs(failed_only=True)
        self.assertEqual(len(failed_jobs), 1)
        self.assertEqual(failed_jobs[0]["job_id"], "job-f1")

        # 5. Stats computation
        stats = self.store.get_stats()
        self.assertEqual(stats["total_jobs"], 2)
        self.assertEqual(stats["completed_count"], 1)
        self.assertEqual(stats["failed_count"], 1)
        self.assertEqual(stats["success_rate"], 50.0)
        self.assertEqual(stats["avg_duration_seconds"], 11.5)  # (15 + 8) / 2
        self.assertEqual(stats["failure_categories"].get("missing_dependency"), 1)

    def test_ignore_intermediate_event_job(self) -> None:
        # Running event should not be recorded in terminal history
        events = [
            {"event": "started", "job_id": "job-r1", "sequence": 1, "timestamp": 100.0, "progress": 0},
            {"event": "progress", "job_id": "job-r1", "sequence": 2, "timestamp": 102.0, "progress": 50},
        ]
        snap = {"job_id": "job-r1", "accepted_count": 2, "highest_sequence": 2, "latest": events[-1]}
        self.assertFalse(self.store.record_job(events, snap))
        self.assertEqual(len(self.store.list_jobs()), 0)


class HttpHistoryEndpointsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_file.close()
        self.store = HistoryStore(db_path=self.temp_file.name)
        self.token = "a" * 16

        self.server, self.log = build_server(
            "127.0.0.1",
            0,
            self.token,
            history_store=self.store,
        )
        self.port = self.server.server_port
        import threading
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        import os
        try:
            os.remove(self.temp_file.name)
        except OSError:
            pass

    def test_http_get_history_and_stats(self) -> None:
        # Post a completed job event sequence
        post_url = f"http://127.0.0.1:{self.port}/v1/events"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

        start_payload = {
            "schema_version": 1,
            "event": "started",
            "job_id": "job-http-1",
            "sequence": 1,
            "timestamp": "2026-01-01T00:00:00.000Z",
            "elapsed_seconds": 0,
            "progress": 0,
            "is_failure": False,
        }
        req = urllib.request.Request(post_url, data=json.dumps(start_payload).encode(), headers=headers)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 202)

        comp_payload = {
            "schema_version": 1,
            "event": "completed",
            "job_id": "job-http-1",
            "sequence": 2,
            "timestamp": "2026-01-01T00:00:10.000Z",
            "elapsed_seconds": 10,
            "progress": 100,
            "exit_code": 0,
            "is_failure": False,
        }
        req = urllib.request.Request(post_url, data=json.dumps(comp_payload).encode(), headers=headers)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 202)

        # GET /v1/history
        get_hist_url = f"http://127.0.0.1:{self.port}/v1/history?limit=10"
        req = urllib.request.Request(get_hist_url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            self.assertEqual(data["status"], "ok")
            self.assertEqual(len(data["jobs"]), 1)
            self.assertEqual(data["jobs"][0]["job_id"], "job-http-1")
            self.assertFalse(data["jobs"][0]["is_failure"])

        # GET /v1/history/stats
        get_stats_url = f"http://127.0.0.1:{self.port}/v1/history/stats"
        req = urllib.request.Request(get_stats_url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            self.assertEqual(data["stats"]["total_jobs"], 1)
            self.assertEqual(data["stats"]["completed_count"], 1)
            self.assertEqual(data["stats"]["success_rate"], 100.0)


if __name__ == "__main__":
    unittest.main()
