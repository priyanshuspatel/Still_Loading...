"""State engine tests. They do not open a socket to the UNO Q."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "mac-agent"))

from http_api import build_server  # noqa: E402
from lights import LightPublisher  # noqa: E402
from sender import post_event  # noqa: E402
from state_engine import EngineConfig, StateEngine  # noqa: E402

TOKEN = "test-token-0123456789"


def event(name: str, sequence: int, progress: int = 0, job_id: str = "job-1", **extra) -> dict:
    message = {
        "schema_version": 1,
        "event": name,
        "job_id": job_id,
        "sequence": sequence,
        "timestamp": "2026-01-01T00:00:00.000Z",
        "elapsed_seconds": 0,
        "progress": progress,
        "is_failure": name == "failed",
    }
    if name == "failed":
        message["message"] = "Simulated build error"
        message["exit_code"] = 1
    if name == "completed":
        message["progress"] = 100
        message["exit_code"] = 0
    message.update(extra)
    return message


class StateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.seen = []
        self.engine = StateEngine(
            EngineConfig(heartbeat_timeout_s=6, slow_progress_gap_s=6),
            on_change=self.seen.append,
        )

    def test_starts_idle_then_running(self) -> None:
        self.assertEqual(self.engine.view.state, "idle")
        view = self.engine.apply(event("started", 1), now=0)
        self.assertEqual(view.state, "running")
        self.assertEqual(view.progress, 0)
        self.assertEqual(self.seen[-1].reason, "started")

    def test_missing_heartbeat_is_a_suspected_stall_and_can_recover(self) -> None:
        self.engine.apply(event("started", 1), now=0)
        self.engine.apply(event("heartbeat", 2), now=2)
        self.assertEqual(self.engine.tick(7.9).state, "running")
        stalled = self.engine.tick(8)
        self.assertEqual(stalled.state, "suspected_stall")
        self.assertEqual(stalled.reason, "heartbeat_timeout")
        self.assertNotEqual(stalled.state, "failed")
        recovered = self.engine.apply(event("heartbeat", 3), now=9)
        self.assertEqual(recovered.state, "running")

    def test_progress_after_a_stall_does_not_declare_failure(self) -> None:
        self.engine.apply(event("started", 1), now=0)
        self.assertEqual(self.engine.tick(6).state, "suspected_stall")
        view = self.engine.apply(event("progress", 2, progress=30), now=7)
        self.assertEqual(view.state, "suspected_stall")
        self.assertEqual(view.progress, 30)
        self.assertNotEqual(view.state, "failed")

    def test_slow_progress_and_return_to_running(self) -> None:
        self.engine.apply(event("started", 1), now=0)
        self.engine.apply(event("progress", 2, progress=15), now=3)
        self.assertEqual(self.engine.view.state, "running")
        slow = self.engine.apply(event("progress", 3, progress=40), now=11)
        self.assertEqual(slow.state, "slow")
        resumed = self.engine.apply(event("progress", 4, progress=55), now=14)
        self.assertEqual(resumed.state, "running")

    def test_failure_and_completion_are_terminal(self) -> None:
        failed = self.engine.apply(event("failed", 1, progress=40), now=1)
        self.assertEqual(failed.state, "failed")
        ignored = self.engine.apply(event("heartbeat", 2), now=2)
        self.assertEqual(ignored.state, "failed")

        other = StateEngine(EngineConfig())
        done = other.apply(event("completed", 1), now=1)
        self.assertEqual(done.state, "completed")
        self.assertEqual(done.progress, 100)
        self.assertEqual(other.apply(event("heartbeat", 2), now=3).state, "completed")

    def test_duplicate_and_stale_sequences_do_not_move_the_state(self) -> None:
        self.engine.apply(event("started", 1), now=0)
        self.engine.apply(event("heartbeat", 3, progress=10), now=2)
        duplicate = self.engine.apply(event("heartbeat", 3, progress=99), now=3)
        self.assertEqual(duplicate.progress, 10)
        stale = self.engine.apply(event("progress", 2, progress=50), now=4)
        self.assertEqual(stale.progress, 10)
        self.assertEqual(stale.state, "running")

    def test_invalid_event_is_ignored(self) -> None:
        self.engine.apply(event("started", 1), now=0)
        view = self.engine.apply({"event": "exploded"}, now=1)
        self.assertEqual(view.state, "running")
        self.assertEqual(view.job_id, "job-1")

    def test_a_new_job_becomes_the_focus(self) -> None:
        self.engine.apply(event("completed", 1, job_id="job-a"), now=0)
        view = self.engine.apply(event("started", 1, job_id="job-b"), now=1)
        self.assertEqual(view.state, "running")
        self.assertEqual(view.job_id, "job-b")
        self.assertEqual(self.engine.tick(20).job_id, "job-b")
        self.assertEqual(self.engine.tick(20).state, "suspected_stall")


class PublisherTests(unittest.TestCase):
    def test_state_file_has_no_secret_and_bridge_import_is_optional(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lights.json"
            publisher = LightPublisher(path)
            engine = StateEngine(on_change=publisher.show)
            engine.apply(event("started", 1), now=0)
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["state"], "running")
        self.assertEqual(payload["code"], 1)
        self.assertNotIn("token", payload)


class ReceiverHookTests(unittest.TestCase):
    def test_accepted_event_updates_the_engine_and_keeps_the_http_body(self) -> None:
        engine = StateEngine()
        httpd, _log = build_server("127.0.0.1", 0, TOKEN, engine=engine)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{httpd.server_address[1]}"
            result = post_event(url, TOKEN, event("started", 1, job_id="hook-job"))
            self.assertEqual(result["delivery"], "accepted")
            self.assertEqual(result["http_status"], 202)
            self.assertFalse(result["board_recorded_failure"])
            self.assertEqual(engine.view.state, "running")
            self.assertEqual(engine.view.job_id, "hook-job")
            duplicate = post_event(url, TOKEN, event("started", 1, job_id="hook-job"))
            self.assertEqual(duplicate["reason"], "duplicate")
            self.assertEqual(engine.view.sequence, 1)
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
