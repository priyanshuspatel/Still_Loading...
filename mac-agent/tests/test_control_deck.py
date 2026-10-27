"""Control Deck actions stay on the allowlist and use the existing receiver."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "mac-agent"))

from battery import BatteryReading, build_battery_message  # noqa: E402
from control_deck import (  # noqa: E402
    ControlDeck,
    build_control_server,
)
from download_monitor import build_download_message  # noqa: E402
from sender import post_battery, post_download  # noqa: E402
from download_monitor import DownloadSnapshot  # noqa: E402
from gemma_analysis import EvidenceItem, validate_evidence  # noqa: E402
from http_api import build_server  # noqa: E402
from state_engine import EngineConfig, StateEngine  # noqa: E402

TOKEN = "test-token-0123456789"


class FakeProc:
    def __init__(self) -> None:
        self.returncode = None
        self.stdout = None
        self._done = threading.Event()

    def poll(self):
        return self.returncode

    def terminate(self) -> None:
        self.returncode = 0
        self._done.set()

    def kill(self) -> None:
        self.terminate()

    def wait(self, timeout: float | None = None):
        self._done.wait(timeout)
        return self.returncode


class Board:
    def __init__(self) -> None:
        self.engine = StateEngine(
            EngineConfig(heartbeat_timeout_s=0.35, slow_progress_gap_s=0.15)
        )
        self.httpd, _log = build_server("127.0.0.1", 0, TOKEN, engine=self.engine)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.stop = threading.Event()

        def tick() -> None:
            while not self.stop.wait(0.05):
                self.engine.tick(time.monotonic())

        self.ticker = threading.Thread(target=tick, daemon=True)
        self.ticker.start()

    def close(self) -> None:
        self.stop.set()
        self.httpd.shutdown()
        self.httpd.server_close()


def active_download() -> DownloadSnapshot:
    return DownloadSnapshot(
        state="downloading",
        download_id="dl-demo-1",
        filename="notes.zip",
        downloaded_bytes=250,
        total_bytes=1000,
        progress=25,
        progress_known=True,
    )


class ControlDeckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.board = Board()
        self.deck = ControlDeck(
            self.board.base,
            TOKEN,
            read_battery=lambda: BatteryReading(percent=82, charging_state="discharging"),
            make_download_reader=lambda: active_download,
            slow_gap_s=0.2,
            heartbeat_every_s=0.05,
            stall_wait_s=0.8,
            demo_step_s=0,
            demo_plan=[
                ("preview", "battery", 82, "Battery 82%"),
                ("preview", "download", 50, "Download 50%"),
            ],
            gemma_enabled=True,
            analyze=self._analyze,
            spawn=self._spawn,
        )
        self.spawned: list[list[str]] = []
        self.httpd = build_control_server(self.deck, "127.0.0.1", 0)
        self.server = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server.start()
        self.control = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def _spawn(self, argv: list[str]):
        self.spawned.append(list(argv))
        if "battery_monitor.py" in argv[1]:
            message = build_battery_message(
                BatteryReading(percent=82, charging_state="discharging"),
                display_mode="battery",
            )
            post_battery(self.board.base, TOKEN, message)
        if "download_monitor.py" in argv[1]:
            post_download(self.board.base, TOKEN, build_download_message(active_download()))
        return FakeProc()

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.board.close()

    def _analyze(self, excerpt: str, *, exit_code: int, message: str) -> dict:
        from gemma_analysis import AnalysisResult

        cited = ""
        for line in excerpt.splitlines():
            if "non_existent_pkg_xyz" in line:
                cited = line.strip()
                break
        found = bool(cited) and cited in excerpt
        return AnalysisResult(
            diagnosis="The demo job imported a module that is not installed.",
            confidence=0.92,
            evidence=[EvidenceItem(cited or "not-in-log", "The import failed.", found)],
            recommended_action="Install the missing module or change the demo import.",
            severity="error",
            verification_status="verified" if found else "unverified",
            source="gemma",
            category="missing_dependency",
        ).to_explanation_dict()

    def _post(self, path: str, body: dict | None = None) -> tuple[int, dict]:
        data = json.dumps(body or {}).encode("utf-8")
        request = urllib.request.Request(
            self.control + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def _post_error(self, path: str, body: dict) -> tuple[int, dict]:
        data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self.control + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def _get(self, path: str) -> dict:
        with urllib.request.urlopen(self.control + path) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_invalid_control_requests_are_rejected(self) -> None:
        status, body = self._post_error("/v1/control/demo", {"action": "rm", "command": "rm -rf /"})
        self.assertEqual(status, 400)
        self.assertEqual(body["reason"], "forbidden_field")
        status, body = self._post_error("/v1/control/job", {"action": "job_success", "argv": ["rm"]})
        self.assertEqual(status, 400)
        status, body = self._post_error("/v1/control/job", {"action": "not-a-job"})
        self.assertEqual(status, 400)
        self.assertEqual(body["reason"], "unknown_action")

    def test_battery_button_starts_one_monitor_and_reaches_the_receiver(self) -> None:
        status, body = self._post("/v1/control/battery")
        self.assertEqual(status, 200)
        self.assertEqual(len(self.spawned), 1)
        argv = self.spawned[0]
        self.assertTrue(argv[1].endswith("battery_monitor.py"))
        self.assertIn("--mode", argv)
        self.assertIn("battery", argv)
        self.assertNotIn("command", argv)
        self.assertEqual(self.board.engine.battery_view.percent, 82)
        self.assertEqual(self.board.engine.view.state, "battery")
        self.assertEqual(body["state"]["battery"]["percent"], 82)
        self.assertFalse(body["state"]["battery"].get("simulated", False))
        status, _again = self._post("/v1/control/battery")
        self.assertEqual(status, 200)
        self.assertEqual(len(self.spawned), 1)
        self.assertIn("monitor already running", " ".join(event["action"] for event in self.deck.log_entries()))

    def test_download_button_starts_one_monitor_and_reaches_the_receiver(self) -> None:
        status, body = self._post("/v1/control/download")
        self.assertEqual(status, 200)
        self.assertEqual(len(self.spawned), 1)
        argv = self.spawned[0]
        self.assertTrue(argv[1].endswith("download_monitor.py"))
        self.assertEqual(argv[argv.index("--interval") + 1], "0.25")
        self.assertEqual(self.board.engine.download_view.progress, 25)
        self.assertEqual(self.board.engine.view.state, "download")
        self.assertEqual(body["state"]["download"]["downloaded_bytes"], 250)
        self.assertEqual(body["state"]["download"]["total_bytes"], 1000)
        self._post("/v1/control/download")
        self.assertEqual(len(self.spawned), 1)

    def test_stop_and_reset_stop_monitors(self) -> None:
        self._post("/v1/control/battery")
        self._post("/v1/control/download")
        self.assertEqual(len(self.spawned), 2)
        self.assertFalse(self.deck._monitor_running("battery"))
        self.assertTrue(self.deck._monitor_running("download"))
        self._post("/v1/control/download")
        self.assertEqual(len(self.spawned), 2)
        self._post("/v1/control/stop")
        self.assertFalse(self.deck._monitor_running("download"))
        self._post("/v1/control/battery")
        self.assertEqual(len(self.spawned), 3)
        self._post("/v1/control/reset")
        self.assertFalse(self.deck._monitor_running("battery"))

    def test_job_buttons_and_reset(self) -> None:
        status, _body = self._post("/v1/control/job", {"action": "job_success"})
        self.assertEqual(status, 202)
        self.assertTrue(self.deck.wait_idle(5))
        self.assertEqual(self.board.engine.view.state, "completed")
        status, body = self._post("/v1/control/reset")
        self.assertEqual(status, 200)
        self.assertEqual(body["state"]["lights"]["state"], "idle")
        self.assertEqual(self.board.engine.display_mode, "auto")

    def test_monitor_argv_uses_config_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.local.json"
            path.write_text(
                '{"host":"127.0.0.1","port":9,"token":"test-token-0123456789"}',
                encoding="utf-8",
            )
            self.deck.config_path = str(path)
            argv = self.deck.monitor_argv("battery")
            self.assertIn("--config", argv)
            self.assertIn(str(path), argv)
            self.assertEqual(argv[argv.index("--mode") + 1], "battery")
            self.assertNotIn("--url", argv)
            download = self.deck.monitor_argv("download")
            self.assertEqual(download[download.index("--interval") + 1], "0.25")
            self.assertNotIn("--url", download)

    def test_slow_stall_and_completed(self) -> None:
        self.assertEqual(self._post("/v1/control/job", {"action": "job_slow"})[0], 202)
        self.assertTrue(self.deck.wait_idle(5))
        self.assertEqual(self.board.engine.view.state, "slow")
        self.assertEqual(self._post("/v1/control/job", {"action": "completed"})[0], 202)
        self.assertTrue(self.deck.wait_idle(5))
        self.assertEqual(self.board.engine.view.state, "completed")
        self.assertEqual(self._post("/v1/control/job", {"action": "job_stall"})[0], 202)
        self.assertTrue(self.deck.wait_idle(5))
        self.assertEqual(self.board.engine.view.state, "suspected_stall")
        feed = " ".join(event["action"] for event in self.deck.log_entries())
        self.assertIn("suspected stall", feed)

    def test_failure_propagates_verified_gemma_evidence(self) -> None:
        self.assertEqual(self._post("/v1/control/job", {"action": "job_failure"})[0], 202)
        self.assertTrue(self.deck.wait_idle(8))
        self.assertEqual(self.board.engine.view.state, "failed")
        gemma = self._get("/v1/gemma/latest")["gemma"]
        self.assertEqual(gemma["verification_status"], "verified")
        self.assertEqual(gemma["confidence"], 0.92)
        cited = gemma["evidence"][0]["log_line"]
        excerpt = self.deck.snapshot()["job"]["excerpt"]
        self.assertIn(cited, excerpt)
        self.assertTrue(gemma["evidence"][0]["found"])
        checked = validate_evidence(
            type("Parsed", (), {"evidence": [(cited, "The import failed.")]})(),
            excerpt,
        )
        self.assertTrue(checked[0].found)
        missed = validate_evidence(
            type("Parsed", (), {"evidence": [("this line was invented", "no")]})(),
            excerpt,
        )
        self.assertFalse(missed[0].found)

    def test_matrix_events_and_offline(self) -> None:
        matrix = self._get("/v1/matrix")
        self.assertEqual(len(matrix["frame"]), 8)
        self.assertEqual(len(matrix["frame"][0]), 13)
        events = self._get("/v1/events")["events"]
        self.assertTrue(any(event["source"] == "SYSTEM" for event in events))
        self.deck._last_lights = {
            "state": "battery",
            "code": 6,
            "job_id": None,
            "progress": 82,
            "sequence": 0,
            "progress_known": True,
            "display_mode": "battery",
            "charging_state": "discharging",
        }
        self.deck._fetch = lambda _path: None
        snap = self.deck.snapshot()
        self.assertEqual(snap["uno_q"], "offline")
        self.assertEqual(snap["lights"]["progress"], 82)
        self.assertEqual(snap["matrix"]["state"], "battery")

    def test_demo_preview_is_labeled_and_not_posted_as_battery(self) -> None:
        calls = []
        self.deck._post_battery = lambda *args, **kwargs: calls.append(args) or {"delivered": True}
        self.assertEqual(self._post("/v1/control/demo", {"action": "demo"})[0], 202)
        self.assertTrue(self.deck.wait_idle(5))
        self.assertEqual(calls, [])
        self.assertIsNone(self.board.engine.battery_view)
        feed = " ".join(event["action"] for event in self.deck.log_entries())
        self.assertIn("DEMO / SIMULATED", feed)
        telemetry = self._get("/api/telemetry")
        self.assertIn("lights", telemetry)
        self.assertIn("connection", telemetry)

    def test_connection_gemma_and_priority_labels(self) -> None:
        status, body = self._post("/v1/control/connection")
        self.assertEqual(status, 200)
        self.assertEqual(body["state"]["uno_q"], "connected")
        self.assertEqual(body["state"]["display_mode"], "auto")
        self.assertTrue(any("CONNECTED" in event["action"] for event in body["events"]))
        self.deck._fetch = lambda _path: None
        status, body = self._post("/v1/control/connection")
        self.assertEqual(status, 200)
        self.assertEqual(body["state"]["uno_q"], "offline")
        self.assertEqual(body["state"]["lights"]["state"], "idle")
        self.assertTrue(any(event["action"] == "OFFLINE" for event in body["events"]))
        self.deck._last_job = {
            "job_id": "job-gemma",
            "event": "failed",
            "progress": 0,
            "exit_code": 1,
            "is_failure": True,
            "message": "Process exited with code 1",
            "excerpt": "ModuleNotFoundError: No module named 'non_existent_pkg_xyz'",
        }
        status, body = self._post("/v1/control/gemma")
        self.assertEqual(status, 200)
        self.assertEqual(body["state"]["gemma"]["verification_status"], "verified")
        cited = body["state"]["gemma"]["evidence"][0]["log_line"]
        self.assertIn(cited, self.deck._last_job["excerpt"])
        status, body = self._post_error("/v1/control/battery", {"shell": "os.system('rm')"})
        self.assertEqual(status, 400)
        self.assertEqual(body["reason"], "forbidden_field")


if __name__ == "__main__":
    unittest.main()
