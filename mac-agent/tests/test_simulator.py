"""Automated checks for the local job simulator.

Run them from the mac-agent directory:

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simulator import collect_events, validate_event  # noqa: E402


AGENT = Path(__file__).resolve().parents[1] / "job_agent.py"


def event_names(mode: str) -> list[str]:
    return [event["event"] for event in collect_events(mode)]


class ScenarioTests(unittest.TestCase):
    def test_normal_reaches_completion(self) -> None:
        events = collect_events("normal")
        self.assertEqual(events[0]["event"], "started")
        self.assertEqual(events[-1]["event"], "completed")
        self.assertEqual(events[-1]["progress"], 100)
        self.assertEqual(events[-1]["exit_code"], 0)
        self.assertFalse(any(event["event"] == "failed" for event in events))
        self.assertEqual(
            [event["event"] for event in events].count("heartbeat"),
            9,
        )
        self.assertEqual(
            [event["event"] for event in events].count("progress"),
            6,
        )

    def test_slow_keeps_heartbeats_and_reports_less_progress(self) -> None:
        slow = collect_events("slow")
        normal = collect_events("normal")
        slow_heartbeats = [event for event in slow if event["event"] == "heartbeat"]
        normal_heartbeats = [
            event for event in normal if event["event"] == "heartbeat"
        ]
        self.assertEqual(
            [event["elapsed_seconds"] for event in slow_heartbeats],
            [event["elapsed_seconds"] for event in normal_heartbeats],
        )
        self.assertLess(
            sum(event["event"] == "progress" for event in slow),
            sum(event["event"] == "progress" for event in normal),
        )
        self.assertEqual(slow[-1]["event"], "completed")
        self.assertEqual(
            [event["progress"] for event in slow if event["event"] == "progress"],
            [40, 80],
        )

    def test_hang_stops_heartbeats_without_declaring_failure(self) -> None:
        events = collect_events("hang")
        names = [event["event"] for event in events]
        self.assertIn("heartbeat_paused", names)
        self.assertNotIn("failed", names)
        self.assertNotIn("completed", names)
        self.assertEqual(names[-1], "scenario_ended")

        pause_at = names.index("heartbeat_paused")
        self.assertFalse(
            any(name == "heartbeat" for name in names[pause_at + 1 :])
        )
        paused = events[pause_at]
        self.assertEqual(paused["reason"], "simulated_missing_heartbeat")
        self.assertFalse(paused["is_failure"])
        self.assertEqual(paused["elapsed_seconds"], 8.0)

        # Progress can still move after the heartbeat signal stops.
        progress_after = [
            event["progress"]
            for event in events[pause_at + 1 :]
            if event["event"] == "progress"
        ]
        self.assertEqual(progress_after, [45, 60, 75, 90])
        self.assertEqual(events[-1]["outcome"], "missing_heartbeat")
        self.assertFalse(events[-1]["is_failure"])

    def test_fail_is_explicit_and_stops_the_scenario(self) -> None:
        events = collect_events("fail")
        self.assertEqual(events[-1]["event"], "failed")
        self.assertTrue(events[-1]["is_failure"])
        self.assertEqual(events[-1]["exit_code"], 1)
        self.assertEqual(events[-1]["message"], "Simulated build error")
        self.assertEqual(events[-1]["elapsed_seconds"], 10.0)
        self.assertFalse(any(event["event"] == "completed" for event in events))
        self.assertFalse(
            any(event["event"] == "heartbeat_paused" for event in events)
        )
        self.assertEqual(
            [event["elapsed_seconds"] for event in events if event["event"] == "heartbeat"],
            [2.0, 4.0, 6.0, 8.0],
        )

    def test_every_event_shares_one_job_and_valid_shape(self) -> None:
        for mode in ("normal", "slow", "hang", "fail"):
            events = collect_events(mode, job_id="abc12345")
            sequences = [event["sequence"] for event in events]
            self.assertEqual(sequences, list(range(1, len(events) + 1)))
            for event in events:
                validate_event(event)
                self.assertEqual(event["job_id"], "abc12345")
                self.assertEqual(event["mode"], mode)
                self.assertTrue(event["timestamp"].endswith("Z"))

    def test_heartbeat_at_two_seconds_still_has_zero_progress(self) -> None:
        events = collect_events("normal")
        first_heartbeat = next(
            event for event in events if event["event"] == "heartbeat"
        )
        self.assertEqual(first_heartbeat["elapsed_seconds"], 2.0)
        self.assertEqual(first_heartbeat["progress"], 0)

    def test_unknown_mode_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            collect_events("explode")


class CommandLineTests(unittest.TestCase):
    def test_fast_fail_prints_json_lines(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(AGENT),
                "--mode",
                "fail",
                "--fast",
                "--job-id",
                "cli-job",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        events = [json.loads(line) for line in lines]
        self.assertGreaterEqual(len(events), 2)
        self.assertEqual(events[0]["event"], "started")
        self.assertEqual(events[-1]["event"], "failed")
        self.assertEqual(events[-1]["job_id"], "cli-job")
        self.assertIn("mode=fail", result.stderr)
        # The human-readable banner stays off the JSON stream.
        with self.assertRaises(json.JSONDecodeError):
            json.loads(result.stderr.splitlines()[0])


if __name__ == "__main__":
    unittest.main()
