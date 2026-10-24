"""Phase 5 tests: 8x13 matrix animations, percentages, and Mac battery monitor.

All tests run locally on the Mac using mocked battery output and a loopback
HTTP server. No Arduino hardware or real battery is required.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "mac-agent"))
sys.path.insert(0, str(ROOT / "uno-q"))

from app_lab_main import forward_once  # noqa: E402
from battery import (  # noqa: E402
    BatteryReading,
    BatteryReporter,
    build_battery_message,
    parse_pmset_batt,
    read_macos_battery,
)
from http_api import build_server  # noqa: E402
from matrix_display import (  # noqa: E402
    COLS,
    COMPLETE_HEART_TOTAL_MS,
    COMPLETE_PERCENT_MS,
    ROWS,
    START_INTRO_MS,
    render_completed_check_frame,
    render_failed_frame,
    render_heart_frame,
    render_percentage_frame,
    render_stall_frame,
    render_unavailable_frame,
    render_waiting_dots_frame,
    select_display_frame,
    validate_frame,
)
from messages import ProtocolError, validate_battery_message, validate_message  # noqa: E402
from sender import post_battery, post_display_mode, post_event  # noqa: E402
from state_engine import EngineConfig, StateEngine  # noqa: E402

TOKEN = "test-token-0123456789"


def job_event(name: str, sequence: int, progress: int = 0, job_id: str = "job-1", **extra) -> dict:
    payload = {
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
        payload["message"] = "Process exited with code 1"
        payload["exit_code"] = 1
    elif name == "completed":
        payload["progress"] = 100
        payload["exit_code"] = 0
    payload.update(extra)
    return payload


class MatrixFrameTests(unittest.TestCase):
    def test_heart_and_waiting_frames_have_valid_8x13_dimensions_and_pixels(self) -> None:
        heart = render_heart_frame(brightness=5)
        validate_frame(heart)
        self.assertEqual(len(heart), ROWS)
        self.assertEqual(len(heart[0]), COLS)
        lit = sum(1 for r in heart for cell in r if cell > 0)
        self.assertGreater(lit, 15)

        for step in range(3):
            dots = render_waiting_dots_frame(active_dot=step, progress=40, slow=False)
            validate_frame(dots)
            self.assertGreater(dots[3][3], 0)
            self.assertGreater(dots[3][6], 0)
            self.assertGreater(dots[3][9], 0)

    def test_all_progress_values_0_to_100_render_safely(self) -> None:
        key_samples = {0, 1, 10, 34, 99, 100}
        seen_samples: dict[int, list[list[int]]] = {}
        for pct in range(0, 101):
            frame = render_percentage_frame(pct)
            validate_frame(frame)
            if pct in key_samples:
                seen_samples[pct] = frame

        # Key percentages must be distinct from one another on the 8x13 grid.
        for a in (1, 10, 34, 99, 100):
            for b in (1, 10, 34, 99, 100):
                if a != b:
                    self.assertNotEqual(seen_samples[a], seen_samples[b])

        # 100 lights the full row-7 completion cue.
        self.assertTrue(all(cell > 0 for cell in seen_samples[100][7]))

        with self.assertRaises(ValueError):
            render_percentage_frame(-1)
        with self.assertRaises(ValueError):
            render_percentage_frame(101)

    def test_unknown_progress_never_displays_fabricated_percentage(self) -> None:
        for ms in (0, 500, START_INTRO_MS + 100, START_INTRO_MS + 5000, START_INTRO_MS + 7000):
            kind, frame = select_display_frame("running", progress=0, elapsed_ms=ms, progress_known=False)
            validate_frame(frame)
            self.assertNotEqual(kind, "percentage")
            self.assertNotEqual(frame, render_percentage_frame(0))

        slow_kind, slow_frame = select_display_frame("slow", progress=0, elapsed_ms=500, progress_known=False)
        validate_frame(slow_frame)
        self.assertEqual(slow_kind, "slow_waiting")

    def test_state_to_animation_mapping_and_distinct_outcomes(self) -> None:
        # Running starts with two heart blinks, then cycles percentage -> waiting dots -> heartbeat.
        k_start, f_start = select_display_frame("running", progress=34, elapsed_ms=100, progress_known=True)
        self.assertEqual(k_start, "start_heart")
        validate_frame(f_start)

        k_pct, f_pct = select_display_frame("running", progress=34, elapsed_ms=START_INTRO_MS + 200, progress_known=True)
        self.assertEqual(k_pct, "percentage")
        self.assertEqual(f_pct, render_percentage_frame(34))

        k_wait, f_wait = select_display_frame("running", progress=34, elapsed_ms=START_INTRO_MS + 5000, progress_known=True)
        self.assertEqual(k_wait, "waiting_dots")
        validate_frame(f_wait)

        k_hb, f_hb = select_display_frame("running", progress=34, elapsed_ms=START_INTRO_MS + 7000, progress_known=True)
        self.assertEqual(k_hb, "heartbeat")
        validate_frame(f_hb)

        # Slow and suspected_stall are distinct from failed.
        k_slow, f_slow = select_display_frame("slow", progress=34, elapsed_ms=200, progress_known=True)
        self.assertEqual(k_slow, "slow_percentage")
        k_stall, f_stall = select_display_frame("suspected_stall", progress=34, elapsed_ms=100, progress_known=True)
        self.assertEqual(k_stall, "suspected_stall")

        # Completed plays heart -> 100 -> settled check, and is distinct from failed X.
        k_c1, f_c1 = select_display_frame("completed", progress=100, elapsed_ms=100)
        k_c2, f_c2 = select_display_frame("completed", progress=100, elapsed_ms=COMPLETE_HEART_TOTAL_MS + 100)
        k_c3, f_c3 = select_display_frame("completed", progress=100, elapsed_ms=COMPLETE_PERCENT_MS + 500)
        self.assertEqual((k_c1, k_c2, k_c3), ("completed_heart", "completed_100", "completed_check"))

        k_fail, f_fail = select_display_frame("failed", progress=34, elapsed_ms=5000)
        self.assertEqual(k_fail, "failed_x")
        self.assertNotEqual(f_fail, f_c1)
        self.assertNotEqual(f_fail, f_c2)
        self.assertNotEqual(f_fail, f_c3)
        self.assertNotEqual(f_fail, f_stall)
        self.assertNotEqual(f_fail, f_slow)
        self.assertNotEqual(render_completed_check_frame(), render_failed_frame())
        self.assertNotEqual(render_stall_frame(), render_failed_frame())


class BatteryParsingAndDeduplicationTests(unittest.TestCase):
    def test_parses_charging_discharging_and_full_outputs(self) -> None:
        charging_out = (
            "Now drawing from 'AC Power'\n"
            " -InternalBattery-0 (id=1234567)\t34%; charging; 1:12 remaining present: true\n"
        )
        discharging_out = (
            "Now drawing from 'Battery Power'\n"
            " -InternalBattery-0 (id=1234567)\t87%; discharging; 4:05 remaining present: true\n"
        )
        full_out = (
            "Now drawing from 'AC Power'\n"
            " -InternalBattery-0 (id=1234567)\t100%; charged; 0:00 remaining present: true\n"
        )
        ac_not_charging_out = (
            "Now drawing from 'AC Power'\n"
            " -InternalBattery-0 (id=1234567)\t78%; AC attached; not charging present: true\n"
        )

        self.assertEqual(parse_pmset_batt(charging_out), BatteryReading(34, "charging"))
        self.assertEqual(parse_pmset_batt(discharging_out), BatteryReading(87, "discharging"))
        self.assertEqual(parse_pmset_batt(full_out), BatteryReading(100, "full"))
        # AC power attached without "charging" must not be mislabeled as charging.
        self.assertEqual(parse_pmset_batt(ac_not_charging_out), BatteryReading(78, "unknown"))

    def test_invalid_or_unavailable_battery_data_returns_none(self) -> None:
        self.assertIsNone(parse_pmset_batt(""))
        self.assertIsNone(parse_pmset_batt("Now drawing from 'AC Power'\nNo batteries available\n"))
        self.assertIsNone(parse_pmset_batt(" -InternalBattery-0\t150%; charging\n"))

        def failing_cmd(*_args, **_kwargs):
            raise FileNotFoundError("pmset missing")

        self.assertIsNone(read_macos_battery(run_cmd=failing_cmd))

        def nonzero_cmd(*_args, **_kwargs):
            return subprocess.CompletedProcess(["pmset"], returncode=1, stdout="", stderr="err")

        self.assertIsNone(read_macos_battery(run_cmd=nonzero_cmd))

    def test_duplicate_battery_readings_do_not_flood_receiver(self) -> None:
        readings = [
            BatteryReading(55, "charging"),
            BatteryReading(55, "charging"),
            BatteryReading(56, "charging"),
        ]
        sent_messages: list[dict] = []

        def fake_read():
            return readings.pop(0)

        def fake_send(msg: dict) -> dict:
            sent_messages.append(msg)
            return {"delivered": True, "delivery": "accepted"}

        reporter = BatteryReporter(fake_send, read_fn=fake_read)
        first = reporter.poll_once()
        second = reporter.poll_once()
        third = reporter.poll_once()

        self.assertEqual(first["status"], "sent")
        self.assertEqual(second["status"], "unchanged")
        self.assertFalse(second["sent"])
        self.assertEqual(third["status"], "sent")
        self.assertEqual(len(sent_messages), 2)

    def test_battery_validation_rejects_extra_fields_and_job_log_rejects_battery(self) -> None:
        valid = build_battery_message(BatteryReading(80, "discharging"))
        validate_battery_message(valid)

        # Battery messages cannot be accepted as job events.
        with self.assertRaises(ProtocolError):
            validate_message(valid)

        with self.assertRaises(ProtocolError):
            validate_battery_message({**valid, "secret": "do-not-allow"})
        with self.assertRaises(ProtocolError):
            validate_battery_message({**valid, "percent": 120})


class PriorityAndIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = StateEngine(EngineConfig(heartbeat_timeout_s=6, slow_progress_gap_s=6))
        self.httpd, self.job_log = build_server("127.0.0.1", 0, TOKEN, engine=self.engine)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def test_battery_messages_do_not_create_or_overwrite_active_or_failed_job_state(self) -> None:
        post_event(self.base, TOKEN, job_event("started", 1, job_id="build-1"))
        post_event(self.base, TOKEN, job_event("progress", 2, progress=42, job_id="build-1"))
        self.assertEqual(self.engine.view.state, "running")
        self.assertEqual(self.engine.view.progress, 42)
        self.assertTrue(self.engine.view.progress_known)

        # Send a battery update while the job is active.
        batt_msg = build_battery_message(BatteryReading(88, "charging"))
        res = post_battery(self.base, TOKEN, batt_msg)
        self.assertTrue(res["delivered"])

        # Job state still takes priority and no fake job was created.
        self.assertEqual(self.engine.view.state, "running")
        self.assertEqual(self.engine.view.progress, 42)
        self.assertEqual(self.engine.view.job_id, "build-1")
        self.assertIsNone(self.job_log.snapshot("battery"))

        # Even if the job fails, battery updates in auto mode do not hide the failure.
        post_event(self.base, TOKEN, job_event("failed", 3, progress=42, job_id="build-1"))
        post_battery(self.base, TOKEN, build_battery_message(BatteryReading(89, "charging")))
        self.assertEqual(self.engine.view.state, "failed")
        self.assertEqual(self.engine.view.code, 4)

    def test_explicit_battery_mode_and_unavailable_indicator(self) -> None:
        # Selecting battery mode before any reading arrives shows battery_unavailable (code 8).
        mode_res = post_display_mode(self.base, TOKEN, "battery")
        self.assertTrue(mode_res["delivered"])
        self.assertEqual(self.engine.view.state, "battery_unavailable")
        self.assertEqual(self.engine.view.code, 8)
        kind, frame = select_display_frame(self.engine.view.state, self.engine.view.progress)
        self.assertEqual(kind, "battery_unavailable")
        self.assertEqual(frame, render_unavailable_frame())

        # Sending a charging battery reading updates the display to code 7 (battery_charging, 34%).
        post_battery(self.base, TOKEN, build_battery_message(BatteryReading(34, "charging")))
        self.assertEqual(self.engine.view.state, "battery_charging")
        self.assertEqual(self.engine.view.code, 7)
        self.assertEqual(self.engine.view.progress, 34)

        calls: list[tuple[int, int]] = []
        status, _pair = forward_once([self.base], TOKEN, lambda c, p: calls.append((c, p)), None)
        self.assertIn("forwarded battery_charging code=7 progress=34", status)
        self.assertEqual(calls, [(7, 34)])

    def test_return_to_battery_on_job_completion_and_stall_recovery(self) -> None:
        post_battery(
            self.base,
            TOKEN,
            build_battery_message(
                BatteryReading(76, "discharging"),
                display_mode="auto",
                return_to_battery=True,
            ),
        )
        # Idle returns to battery when return_to_battery is enabled.
        self.assertEqual(self.engine.view.state, "battery")
        self.assertEqual(self.engine.view.progress, 76)

        # Starting a job immediately preempts battery display.
        self.engine.apply(job_event("started", 1, job_id="job-r"), now=0.0)
        self.assertEqual(self.engine.view.state, "running")
        self.assertFalse(self.engine.view.progress_known)

        # Missing heartbeat enters suspected_stall, not failed; returning heartbeat restores running.
        self.assertEqual(self.engine.tick(7.0).state, "suspected_stall")
        self.assertEqual(self.engine.apply(job_event("heartbeat", 2, job_id="job-r"), now=8.0).state, "running")

        # When the job completes and return_to_battery=True, display returns to battery.
        self.engine.apply(job_event("completed", 3, job_id="job-r"), now=10.0)
        self.assertEqual(self.engine.job_view.state, "completed")
        self.assertEqual(self.engine.view.state, "battery")
        self.assertEqual(self.engine.view.code, 6)
        self.assertEqual(self.engine.view.progress, 76)

    def test_battery_and_mode_endpoints_require_bearer_token(self) -> None:
        bad_batt = post_battery(
            self.base,
            "wrong-token-0123456789",
            build_battery_message(BatteryReading(50, "discharging")),
        )
        self.assertEqual(bad_batt["delivery"], "unauthorized")
        self.assertEqual(bad_batt["http_status"], 401)

        bad_mode = post_display_mode(self.base, "wrong-token-0123456789", "battery")
        self.assertEqual(bad_mode["delivery"], "unauthorized")
        self.assertEqual(bad_mode["http_status"], 401)

        req = urllib.request.Request(self.base + "/v1/battery", method="GET")
        with self.assertRaises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(req, timeout=2)
        self.assertEqual(denied.exception.code, 401)


if __name__ == "__main__":
    unittest.main()
