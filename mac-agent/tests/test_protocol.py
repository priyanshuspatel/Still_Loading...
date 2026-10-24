"""Protocol tests. They use a receiver on 127.0.0.1 and never touch the UNO Q."""

from __future__ import annotations

import json
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "mac-agent"))

from http_api import build_server  # noqa: E402
from messages import JobLog, ProtocolError, validate_message  # noqa: E402
from sender import events_for_board, get_job, post_event  # noqa: E402
from simulator import collect_events  # noqa: E402

TOKEN = "test-token-0123456789"
SCHEMA_PATH = ROOT / "shared" / "message_schema.json"


class LocalReceiver:
    def __init__(self) -> None:
        self.httpd, self.log = build_server("127.0.0.1", 0, TOKEN, job_log=JobLog())
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def sample(event: str = "heartbeat", sequence: int = 1, **extra) -> dict:
    message = {
        "schema_version": 1,
        "event": event,
        "job_id": "job-1",
        "sequence": sequence,
        "timestamp": "2026-01-01T00:00:02.000Z",
        "elapsed_seconds": 2,
        "progress": 0,
        "is_failure": False,
    }
    message.update(extra)
    return message


class SchemaTests(unittest.TestCase):
    def test_schema_file_matches_the_code(self) -> None:
        document = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(set(document["wire_events"]), {"started", "heartbeat", "progress", "failed", "completed"})
        self.assertEqual(
            set(document["simulator_only_events"]),
            {"heartbeat_paused", "scenario_ended"},
        )

    def test_simulator_wire_events_validate(self) -> None:
        for mode in ("normal", "slow", "fail"):
            for event in events_for_board(collect_events(mode)):
                validate_message(event)

    def test_unknown_event_and_bad_values_are_rejected(self) -> None:
        with self.assertRaises(ProtocolError) as unknown:
            validate_message(sample(event="exploded"))
        self.assertEqual(unknown.exception.reason, "unknown_event")

        with self.assertRaises(ProtocolError) as progress:
            validate_message(sample(progress=150))
        self.assertEqual(progress.exception.reason, "invalid_field")

        with self.assertRaises(ProtocolError):
            validate_message(sample(sequence="1"))

        with self.assertRaises(ProtocolError) as malformed:
            from messages import parse_json_object

            parse_json_object(b"this is not json")
        self.assertEqual(malformed.exception.reason, "malformed_json")

    def test_simulator_only_events_are_not_wire_messages(self) -> None:
        hang = collect_events("hang")
        names = [event["event"] for event in hang]
        self.assertIn("heartbeat_paused", names)
        self.assertIn("scenario_ended", names)
        forwarded = events_for_board(hang)
        self.assertFalse(any(event["event"] == "heartbeat_paused" for event in forwarded))
        self.assertFalse(any(event["event"] == "scenario_ended" for event in forwarded))
        self.assertTrue(any(event["event"] == "progress" for event in forwarded))


class SequenceTests(unittest.TestCase):
    def test_duplicate_and_stale_sequences_are_refused(self) -> None:
        log = JobLog()
        log.accept(sample(sequence=1))
        log.accept(sample(sequence=3))
        with self.assertRaises(ProtocolError) as duplicate:
            log.accept(sample(sequence=3, progress=10))
        self.assertEqual(duplicate.exception.reason, "duplicate")
        with self.assertRaises(ProtocolError) as stale:
            log.accept(sample(sequence=2))
        self.assertEqual(stale.exception.reason, "stale")
        self.assertEqual(log.latest("job-1")["progress"], 0)
        self.assertEqual(len(log.events("job-1")), 2)

    def test_another_job_keeps_its_own_sequence(self) -> None:
        log = JobLog()
        log.accept(sample(sequence=5))
        other = sample(sequence=1, job_id="job-2")
        log.accept(other)
        self.assertEqual(log.latest("job-2")["sequence"], 1)

    def test_events_after_a_terminal_event_are_refused(self) -> None:
        log = JobLog()
        log.accept(
            sample(
                event="completed",
                sequence=1,
                progress=100,
                exit_code=0,
                elapsed_seconds=20,
            )
        )
        with self.assertRaises(ProtocolError) as refused:
            log.accept(sample(event="heartbeat", sequence=2))
        self.assertEqual(refused.exception.reason, "terminal")


class HttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.receiver = LocalReceiver()

    def tearDown(self) -> None:
        self.receiver.close()

    def test_normal_fail_scenario_is_accepted_and_can_be_read_back(self) -> None:
        events = events_for_board(collect_events("fail", job_id="fail-job"))
        results = [
            post_event(self.receiver.base_url, TOKEN, event) for event in events
        ]
        self.assertTrue(all(result["delivered"] for result in results))
        self.assertTrue(results[-1]["board_recorded_failure"])
        self.assertFalse(any(result["board_recorded_failure"] for result in results[:-1]))
        readback = get_job(self.receiver.base_url, TOKEN, "fail-job")
        self.assertEqual(readback["delivery"], "ok")
        self.assertEqual(readback["body"]["latest"]["event"], "failed")
        self.assertEqual(readback["body"]["accepted_count"], len(events))

    def test_malformed_duplicate_and_bad_token_do_not_stick(self) -> None:
        first = post_event(self.receiver.base_url, TOKEN, sample())
        self.assertEqual(first["delivery"], "accepted")

        duplicate = post_event(self.receiver.base_url, TOKEN, sample())
        self.assertEqual(duplicate["delivery"], "rejected")
        self.assertEqual(duplicate["reason"], "duplicate")
        self.assertFalse(duplicate["board_recorded_failure"])

        stale = post_event(
            self.receiver.base_url,
            TOKEN,
            sample(sequence=1),
        )
        self.assertEqual(stale["reason"], "duplicate")

        newer = post_event(self.receiver.base_url, TOKEN, sample(sequence=4))
        self.assertEqual(newer["delivery"], "accepted")
        older = post_event(self.receiver.base_url, TOKEN, sample(sequence=2))
        self.assertEqual(older["reason"], "stale")

        malformed = post_event(
            self.receiver.base_url,
            TOKEN,
            {"event": "heartbeat", "job_id": "job-1"},
        )
        self.assertEqual(malformed["delivery"], "rejected")
        self.assertEqual(malformed["reason"], "missing_field")

        unauthorized = post_event(self.receiver.base_url, "wrong-token-0123456789", sample(sequence=5))
        self.assertEqual(unauthorized["delivery"], "unauthorized")
        self.assertEqual(len(self.receiver.log.events("job-1")), 2)

    def test_health_has_no_job_data(self) -> None:
        import urllib.request

        with urllib.request.urlopen(self.receiver.base_url + "/health", timeout=2) as response:
            body = json.loads(response.read().decode("utf-8"))
        self.assertEqual(body, {"status": "ok", "service": "still-loading"})
        self.assertNotIn("job_id", body)

    def test_hang_forwarding_does_not_record_a_failure(self) -> None:
        events = events_for_board(collect_events("hang", job_id="hang-job"))
        for event in events:
            result = post_event(self.receiver.base_url, TOKEN, event)
            self.assertEqual(result["delivery"], "accepted")
            self.assertFalse(result["board_recorded_failure"])
        names = [event["event"] for event in self.receiver.log.events("hang-job")]
        self.assertNotIn("failed", names)
        self.assertNotIn("heartbeat_paused", names)
        self.assertIn("progress", names)

    def test_connection_error_is_not_a_job_failure(self) -> None:
        result = post_event(
            "http://127.0.0.1:9",
            TOKEN,
            sample(),
            timeout=0.5,
        )
        self.assertEqual(result["delivery"], "connection_error")
        self.assertFalse(result["delivered"])
        self.assertFalse(result["board_recorded_failure"])
        self.assertEqual(self.receiver.log.events("job-1"), [])
