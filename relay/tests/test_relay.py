"""Tests for the telemetry relay proxy."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

import sys
from pathlib import Path

RELAY_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RELAY_DIR))

from telemetry_relay import TelemetryRelay


class TelemetryRelayTests(unittest.TestCase):
    def test_caching_within_ttl(self) -> None:
        relay = TelemetryRelay("http://127.0.0.1:8090", "test-token")
        relay._fetch_endpoint = MagicMock(return_value={"state": "idle", "code": 0})  # type: ignore

        snap1 = relay.get_snapshot()
        snap2 = relay.get_snapshot()

        self.assertIs(snap1, snap2)
        # Should not fetch again within TTL
        self.assertEqual(relay._fetch_endpoint.call_count, 3)  # /v1/lights, /v1/battery, /v1/download once each

    def test_job_details_and_explanation_included(self) -> None:
        relay = TelemetryRelay("http://127.0.0.1:8090", "test-token")

        def mock_fetch(path: str) -> dict:
            if path == "/v1/lights":
                return {
                    "state": "failed",
                    "code": 4,
                    "job_id": "job-crash-1",
                    "progress": 25,
                }
            if path == "/v1/jobs/job-crash-1":
                return {
                    "job_id": "job-crash-1",
                    "latest": {
                        "event": "failed",
                        "progress": 25,
                        "exit_code": 1,
                        "is_failure": True,
                        "message": "Process exited with code 1",
                        "excerpt": "ModuleNotFoundError: No module named 'numpy'",
                    },
                    "excerpt": "ModuleNotFoundError: No module named 'numpy'",
                    "explanation": {
                        "category": "missing_dependency",
                        "summary": "Missing Python module: 'numpy'",
                        "suggestion": "pip install numpy",
                        "confidence": 1.0,
                        "source": "rules",
                    },
                }
            return {}

        relay._fetch_endpoint = MagicMock(side_effect=mock_fetch)  # type: ignore
        snap = relay.get_snapshot()

        self.assertTrue(snap["is_live"])
        self.assertIsNotNone(snap["job"])
        job = snap["job"]
        self.assertEqual(job["job_id"], "job-crash-1")
        self.assertEqual(job["event"], "failed")
        self.assertIn("ModuleNotFoundError", job["excerpt"])
        self.assertEqual(job["explanation"]["category"], "missing_dependency")
        self.assertIn("pip install numpy", job["explanation"]["suggestion"])


if __name__ == "__main__":
    unittest.main()
