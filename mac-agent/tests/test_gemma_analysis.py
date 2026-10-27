"""Gemma evidence checks, watchdog integration, and board-state compatibility.

These tests do not call a live model and do not open a socket to the UNO Q.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "mac-agent"))
sys.path.insert(0, str(ROOT / "relay"))

from explainer import explain_failure  # noqa: E402
from gemma_analysis import (  # noqa: E402
    AnalysisResult,
    analyze_failure_logs,
    citation_found,
    parse_gemma_output,
    redact_for_model,
)
from gemma_client import GemmaClient, GemmaConfig, GemmaTimeout, GemmaUnavailable  # noqa: E402
from history_store import HistoryStore  # noqa: E402
from matrix_display import select_display_frame  # noqa: E402
from messages import validate_message  # noqa: E402
from model_feasibility import HardwareProfile, assess_feasibility  # noqa: E402
from runner import run_process  # noqa: E402
from simulator import format_timestamp  # noqa: E402
from state_engine import EngineConfig, StateEngine  # noqa: E402
from telemetry_relay import TelemetryRelay  # noqa: E402
from watchdog import FailureWatchdog  # noqa: E402

BASELINE = ROOT / "shared" / "fixtures" / "failure_baseline.json"
REAL_LINE = "ConnectionRefusedError: [Errno 61] Connection refused"
SECRET = "super-secret-token-value"
API_SECRET = "abcd1234secret"
URL_SECRET = "s3cret-pass"
SK_SECRET = "sk-live-THISISASECRETKEY12"


def _baseline() -> dict:
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def _connection_log() -> str:
    for case in _baseline()["cases"]:
        if case["id"] == "python_connection_refused":
            return case["log"]
    raise AssertionError("baseline is missing python_connection_refused")


def _gemma_json(log_line: str, *, diagnosis: str = "The socket connection was refused.") -> str:
    return json.dumps(
        {
            "diagnosis": diagnosis,
            "confidence": 0.92,
            "evidence": [
                {"log_line": log_line, "reason": "This line is the failing call."}
            ],
            "recommended_action": "Check that the UNO Q receiver is listening.",
            "severity": "error",
        }
    )


class _ScriptedClient:
    def __init__(self, text: str) -> None:
        self.text = text
        self.prompts: list[str] = []
        self.calls = 0

    def complete(self, prompt: str) -> str:
        self.calls += 1
        self.prompts.append(prompt)
        return self.text


class BaselineTests(unittest.TestCase):
    def test_baseline_has_fifteen_to_twenty_real_logs(self) -> None:
        payload = _baseline()
        cases = payload["cases"]
        self.assertGreaterEqual(len(cases), 15)
        self.assertLessEqual(len(cases), 20)
        self.assertEqual(payload["case_count"], len(cases))
        blob = BASELINE.read_text(encoding="utf-8")
        self.assertNotIn(SECRET, blob)
        self.assertNotIn("sk-", blob)
        self.assertNotIn("AKIA", blob)
        for case in cases:
            self.assertTrue(case["log"].strip())
            self.assertEqual(case["source"], "captured_process")
            explained = explain_failure(
                exit_code=case["exit_code"] or 1,
                message="captured",
                excerpt=case["log"],
            )
            self.assertEqual(explained.category, case["expected_category"])
            last = case["log"].strip().splitlines()[-1].strip()
            if len(" ".join(last.split())) >= 8:
                self.assertTrue(citation_found(last, case["log"]))
        notes = payload["history_rows_without_excerpts"]
        self.assertGreaterEqual(len(notes), 1)
        self.assertTrue(all(item["id"].startswith("history_") for item in notes))


class EvidenceValidationTests(unittest.TestCase):
    def test_valid_citation_from_real_log_is_verified(self) -> None:
        log = _connection_log()
        self.assertIn(REAL_LINE, log)
        client = _ScriptedClient(_gemma_json(REAL_LINE))
        result = analyze_failure_logs(log, exit_code=1, message="receiver", client=client)
        self.assertEqual(result.verification_status, "verified")
        self.assertTrue(result.to_ui_card()["verified"])
        self.assertEqual(result.evidence[0].log_line, REAL_LINE)
        self.assertTrue(result.evidence[0].found)
        self.assertIn(REAL_LINE, client.prompts[0])
        card = result.to_ui_card()
        self.assertEqual(card["title"], "Gemma Failure Analysis")
        self.assertEqual(card["verification_label"], "Evidence verified")
        self.assertEqual(card["confidence_label"], "92%")
        self.assertEqual(card["evidence"][0]["log_line"], REAL_LINE)

    def test_fabricated_citation_stays_unverified(self) -> None:
        log = _connection_log()
        fake = "ConnectionError: receiver unavailable after 99 retries"
        client = _ScriptedClient(_gemma_json(fake, diagnosis="The receiver vanished."))
        result = analyze_failure_logs(log, client=client)
        self.assertEqual(result.verification_status, "unverified")
        self.assertFalse(result.to_ui_card()["verified"])
        self.assertFalse(result.evidence[0].found)
        self.assertEqual(result.evidence[0].log_line, fake)
        self.assertTrue(result.fallback_used)
        self.assertNotEqual(result.source, "rules")

    def test_partial_mismatch_is_not_accepted(self) -> None:
        log = "ConnectionError: receiver unavailable after 3 retries\n"
        mismatch = "ConnectionError: receiver unavailable after 9 retries"
        self.assertFalse(citation_found(mismatch, log))
        self.assertTrue(citation_found("receiver unavailable after 3 retries", log))
        client = _ScriptedClient(_gemma_json(mismatch))
        result = analyze_failure_logs(log, client=client)
        self.assertEqual(result.verification_status, "unverified")

    def test_multiple_lines_require_every_citation(self) -> None:
        log = _connection_log()
        second = "socket.create_connection(('127.0.0.1', 1), timeout=0.4)"
        self.assertIn(second, log)
        payload = {
            "diagnosis": "The connection to the local port was refused.",
            "confidence": 0.8,
            "evidence": [
                {"log_line": REAL_LINE, "reason": "errno 61"},
                {"log_line": second, "reason": "the call site"},
            ],
            "recommended_action": "Start the receiver.",
            "severity": "error",
        }
        good = analyze_failure_logs(log, client=_ScriptedClient(json.dumps(payload)))
        self.assertEqual(good.verification_status, "verified")
        self.assertEqual(len(good.evidence), 2)
        payload["evidence"][1]["log_line"] = "socket.create_connection(('10.9.9.9', 1), timeout=0.4)"
        mixed = analyze_failure_logs(log, client=_ScriptedClient(json.dumps(payload)))
        self.assertEqual(mixed.verification_status, "unverified")
        self.assertEqual(len(mixed.evidence), 2)
        self.assertTrue(mixed.evidence[0].found)
        self.assertFalse(mixed.evidence[1].found)

    def test_empty_logs_do_not_call_the_model(self) -> None:
        client = _ScriptedClient(_gemma_json(REAL_LINE))
        result = analyze_failure_logs("  \n", client=client)
        self.assertEqual(client.calls, 0)
        self.assertEqual(result.verification_status, "unavailable")
        self.assertEqual(result.detail, "empty_logs")
        self.assertFalse(result.to_ui_card()["verified"])

    def test_malformed_model_text_uses_fallback(self) -> None:
        log = _connection_log()
        client = _ScriptedClient("The receiver is probably offline, I think.")
        result = analyze_failure_logs(log, client=client)
        self.assertEqual(result.verification_status, "malformed")
        self.assertEqual(result.source, "fallback")
        self.assertFalse(result.to_ui_card()["verified"])
        self.assertIn("connection", result.diagnosis.lower())

    def test_fenced_json_parses(self) -> None:
        parsed = parse_gemma_output("```json\n" + _gemma_json(REAL_LINE) + "\n```")
        self.assertEqual(parsed.evidence[0][0], REAL_LINE)

    def test_timeout_and_unavailable_do_not_verify(self) -> None:
        log = _connection_log()

        class TimeoutClient:
            def complete(self, prompt: str) -> str:
                raise GemmaTimeout("slow")

        class DownClient:
            def complete(self, prompt: str) -> str:
                raise GemmaUnavailable("connection refused")

        timed = analyze_failure_logs(log, client=TimeoutClient())
        down = analyze_failure_logs(log, client=DownClient())
        self.assertEqual(timed.verification_status, "timeout")
        self.assertEqual(down.verification_status, "unavailable")
        self.assertEqual(timed.source, "fallback")
        self.assertFalse(timed.to_ui_card()["verified"])
        self.assertFalse(down.to_ui_card()["verified"])

    def test_secrets_are_removed_before_the_prompt(self) -> None:
        log = (
            f"Authorization: Bearer {SECRET}\n"
            f"API_KEY={API_SECRET}\n"
            f"https://user:{URL_SECRET}@example.com/hook\n"
            f"{SK_SECRET}\n"
            f"{REAL_LINE}\n"
        )
        client = _ScriptedClient(_gemma_json(REAL_LINE))
        stream = __import__("io").StringIO()
        handler = logging.StreamHandler(stream)
        gemma_log = logging.getLogger("still_loading.gemma")
        gemma_log.addHandler(handler)
        gemma_log.setLevel(logging.INFO)
        try:
            result = analyze_failure_logs(log, client=client)
        finally:
            gemma_log.removeHandler(handler)
        prompt = client.prompts[0]
        redacted = redact_for_model(log)
        for secret in (SECRET, API_SECRET, URL_SECRET, SK_SECRET):
            self.assertNotIn(secret, prompt)
            self.assertNotIn(secret, redacted)
            self.assertNotIn(secret, stream.getvalue())
        self.assertIn("[REDACTED]", prompt)
        self.assertIn(REAL_LINE, prompt)
        self.assertEqual(result.verification_status, "verified")

    def test_explanation_dict_validates_on_the_wire(self) -> None:
        result = analyze_failure_logs(
            _connection_log(),
            client=_ScriptedClient(_gemma_json(REAL_LINE)),
        )
        event = {
            "schema_version": 1,
            "event": "failed",
            "job_id": "gemma-job",
            "sequence": 2,
            "timestamp": format_timestamp(datetime.now(timezone.utc)),
            "elapsed_seconds": 1.0,
            "progress": 10,
            "is_failure": True,
            "exit_code": 1,
            "message": "Process exited with code 1",
            "excerpt": REAL_LINE,
            "explanation": result.to_explanation_dict(),
        }
        checked = validate_message(event)
        self.assertEqual(checked["explanation"]["verification_status"], "verified")
        self.assertLessEqual(len(json.dumps(checked).encode("utf-8")), 8192)


class ClientBudgetTests(unittest.TestCase):
    def test_retry_then_success(self) -> None:
        calls = {"n": 0}

        def transport(payload, timeout_s):
            calls["n"] += 1
            if calls["n"] == 1:
                raise GemmaUnavailable("reset")
            return _gemma_json(REAL_LINE)

        config = GemmaConfig(
            enabled=True,
            base_url="http://127.0.0.1:11434/v1",
            model="gemma2:2b",
            api_key="",
            timeout_s=2,
            max_retries=1,
            max_log_chars=1000,
        )
        text = GemmaClient(config, transport=transport).complete("log")
        self.assertEqual(calls["n"], 2)
        self.assertIn("diagnosis", text)

    def test_timeout_budget_is_bounded(self) -> None:
        def transport(payload, timeout_s):
            time.sleep(min(0.15, max(0.01, timeout_s)))
            raise GemmaTimeout("slow")

        config = GemmaConfig(
            enabled=True,
            base_url="http://127.0.0.1:11434/v1",
            model="gemma2:2b",
            api_key="",
            timeout_s=0.4,
            max_retries=4,
            max_log_chars=500,
        )
        started = time.monotonic()
        with self.assertRaises(GemmaTimeout):
            GemmaClient(config, transport=transport).complete("log")
        self.assertLess(time.monotonic() - started, 1.2)


class WatchdogTests(unittest.TestCase):
    def _started(self, job_id: str = "job-1") -> dict:
        return {
            "schema_version": 1,
            "event": "started",
            "job_id": job_id,
            "sequence": 1,
            "timestamp": "2026-01-01T00:00:00.000Z",
            "elapsed_seconds": 0,
            "progress": 0,
            "is_failure": False,
        }

    def _failed(self, job_id: str = "job-1", excerpt: str | None = None) -> dict:
        event = {
            "schema_version": 1,
            "event": "failed",
            "job_id": job_id,
            "sequence": 2,
            "timestamp": "2026-01-01T00:00:01.000Z",
            "elapsed_seconds": 1,
            "progress": 0,
            "is_failure": True,
            "exit_code": 1,
            "message": "Process exited with code 1",
        }
        if excerpt is not None:
            event["excerpt"] = excerpt
        return event

    def test_failure_reaches_validated_ui_card(self) -> None:
        log = _connection_log()
        engine = StateEngine(EngineConfig(heartbeat_timeout_s=6))
        watchdog = FailureWatchdog(engine, client=_ScriptedClient(_gemma_json(REAL_LINE)), timeout_s=2)
        watchdog.remember_logs("job-1", log)
        watchdog.apply(self._started(), 0)
        view = watchdog.apply(self._failed(), 1)
        self.assertEqual(view.state, "failed")
        self.assertEqual(view.code, 4)
        card = watchdog.ui_payload()
        self.assertIsNotNone(card)
        self.assertEqual(card["verification_status"], "verified")
        self.assertEqual(card["failure_status"], "failed")
        self.assertEqual(card["evidence"][0]["log_line"], REAL_LINE)
        self.assertIn(REAL_LINE, log)

    def test_unavailable_gemma_leaves_the_watchdog_running(self) -> None:
        class Down:
            def complete(self, prompt: str) -> str:
                raise GemmaUnavailable("endpoint down")

        engine = StateEngine(EngineConfig(heartbeat_timeout_s=6))
        watchdog = FailureWatchdog(engine, client=Down(), timeout_s=1)
        watchdog.remember_logs("job-1", _connection_log())
        watchdog.apply(self._started(), 0)
        started = time.monotonic()
        view = watchdog.tick(6)
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertEqual(view.state, "suspected_stall")
        self.assertNotEqual(watchdog.latest.verification_status, "verified")
        self.assertEqual(watchdog.ui_payload()["verification_label"], "Gemma unavailable")
        recovered = watchdog.apply(
            {
                "schema_version": 1,
                "event": "heartbeat",
                "job_id": "job-1",
                "sequence": 2,
                "timestamp": "2026-01-01T00:00:06.000Z",
                "elapsed_seconds": 6,
                "progress": 0,
                "is_failure": False,
            },
            6.2,
        )
        self.assertEqual(recovered.state, "running")

    def test_slow_gemma_does_not_hang_the_watchdog(self) -> None:
        class Slow:
            def complete(self, prompt: str) -> str:
                time.sleep(2)
                return _gemma_json(REAL_LINE)

        engine = StateEngine(EngineConfig(heartbeat_timeout_s=6))
        watchdog = FailureWatchdog(engine, client=Slow(), timeout_s=0.2)
        watchdog.remember_logs("job-1", _connection_log())
        watchdog.apply(self._started(), 0)
        started = time.monotonic()
        view = watchdog.tick(8)
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 1.0)
        self.assertEqual(view.state, "suspected_stall")
        self.assertEqual(watchdog.latest.verification_status, "timeout")
        self.assertFalse(watchdog.ui_payload()["verified"])
        failed = watchdog.apply(self._failed(excerpt=REAL_LINE), 9)
        self.assertEqual(failed.state, "failed")


class BoardCompatibilityTests(unittest.TestCase):
    def test_existing_light_states_ignore_gemma_metadata(self) -> None:
        expected = {
            "battery": "battery_percent",
            "battery_charging": "battery_charging",
            "download": "download_percent",
            "running": "percentage",
            "suspected_stall": "suspected_stall",
            "failed": "failed_x",
            "completed": "completed_100",
        }
        for state, kind in expected.items():
            progress = 100 if state == "completed" else 42
            got, frame = select_display_frame(
                state,
                progress=progress,
                elapsed_ms=2500,
                progress_known=True,
            )
            self.assertEqual(got, kind)
            self.assertEqual(len(frame), 8)
            self.assertEqual(len(frame[0]), 13)

        result = analyze_failure_logs(
            _connection_log(),
            failure_status="failed",
            client=_ScriptedClient(_gemma_json(REAL_LINE)),
        )
        compact = result.compact_board_status()
        self.assertEqual(compact["board_state"], "failed")
        self.assertFalse(compact["renders_diagnosis_on_matrix"])
        kind, _frame = select_display_frame("failed", progress=24, elapsed_ms=0, progress_known=True)
        self.assertEqual(kind, "failed_x")

    def test_battery_download_and_job_priority_stay_intact(self) -> None:
        engine = StateEngine(EngineConfig(heartbeat_timeout_s=6))
        engine.apply_battery(
            {
                "schema_version": 1,
                "kind": "battery",
                "percent": 78,
                "charging_state": "discharging",
                "timestamp": "2026-01-01T00:00:00.000Z",
                "display_mode": "auto",
                "return_to_battery": True,
            }
        )
        self.assertEqual(engine.view.state, "battery")
        self.assertEqual(engine.view.code, 6)

        engine.apply(
            {
                "schema_version": 1,
                "event": "started",
                "job_id": "build-1",
                "sequence": 1,
                "timestamp": "2026-01-01T00:00:01.000Z",
                "elapsed_seconds": 0,
                "progress": 0,
                "is_failure": False,
            },
            1,
        )
        engine.apply_battery(
            {
                "schema_version": 1,
                "kind": "battery",
                "percent": 77,
                "charging_state": "charging",
                "timestamp": "2026-01-01T00:00:02.000Z",
            }
        )
        self.assertEqual(engine.view.state, "running")
        self.assertEqual(engine.view.job_id, "build-1")

        engine.apply(
            {
                "schema_version": 1,
                "event": "failed",
                "job_id": "build-1",
                "sequence": 2,
                "timestamp": "2026-01-01T00:00:03.000Z",
                "elapsed_seconds": 2,
                "progress": 20,
                "is_failure": True,
                "exit_code": 1,
                "message": "Process exited with code 1",
                "explanation": analyze_failure_logs(
                    _connection_log(),
                    client=_ScriptedClient(_gemma_json(REAL_LINE)),
                ).to_explanation_dict(),
            },
            3,
        )
        engine.apply_battery(
            {
                "schema_version": 1,
                "kind": "battery",
                "percent": 76,
                "charging_state": "charging",
                "timestamp": "2026-01-01T00:00:04.000Z",
            }
        )
        self.assertEqual(engine.view.state, "failed")
        self.assertEqual(engine.view.code, 4)

        download_engine = StateEngine()
        download_engine.apply_download(
            {
                "schema_version": 1,
                "kind": "download",
                "download_id": "chrome-1",
                "state": "downloading",
                "downloaded_bytes": 40,
                "total_bytes": 100,
                "progress": 40,
                "progress_known": True,
                "timestamp": "2026-01-01T00:00:00.000Z",
            },
            now=1,
        )
        self.assertEqual(download_engine.view.state, "download")
        self.assertEqual(download_engine.view.progress, 40)

    def test_gemma_placement_is_off_the_board(self) -> None:
        uno = assess_feasibility(
            HardwareProfile(
                platform_system="Linux",
                machine="aarch64",
                cpu_count=4,
                total_memory_mb=2048,
                available_memory_mb=700,
                python_version="3.11.2",
            )
        )
        self.assertTrue(uno.is_uno_q_environment)
        self.assertEqual(uno.gemma_placement, "disabled_on_board")
        self.assertEqual(uno.recommended_engine, "rules")


class HistoryAndRunnerTests(unittest.TestCase):
    def test_history_keeps_verified_evidence_for_the_ui(self) -> None:
        result = analyze_failure_logs(
            _connection_log(),
            client=_ScriptedClient(_gemma_json(REAL_LINE)),
        )
        with tempfile.NamedTemporaryFile(suffix=".db") as handle:
            store = HistoryStore(db_path=handle.name)
            explanation = result.to_explanation_dict()
            snapshot = {
                "job_id": "job-gemma",
                "accepted_count": 2,
                "highest_sequence": 2,
                "latest": {
                    "event": "failed",
                    "timestamp": 2000.0,
                    "elapsed_seconds": 4,
                    "progress": 10,
                    "exit_code": 1,
                    "is_failure": True,
                    "message": "Process exited with code 1",
                },
                "excerpt": REAL_LINE,
                "explanation": explanation,
            }
            events = [
                {"event": "started", "timestamp": 1000.0},
                snapshot["latest"],
            ]
            self.assertTrue(store.record_job(events, snapshot))
            stored = store.list_jobs(limit=5)[0]
            self.assertEqual(stored["explanation"]["verification_status"], "verified")
            self.assertEqual(stored["explanation"]["evidence"][0]["log_line"], REAL_LINE)
            card_status = stored["explanation"]["verification_status"]
            self.assertEqual(card_status, "verified")

    def test_runner_uses_gemma_only_when_enabled(self) -> None:
        import gemma_analysis

        previous = os.environ.get("GEMMA_ENABLED")
        original = gemma_analysis.analyze_failure_logs
        os.environ["GEMMA_ENABLED"] = "1"

        def fake_analyze(logs, **kwargs):
            return AnalysisResult(
                diagnosis="Missing Python module: 'non_existent_pkg_xyz'",
                confidence=0.91,
                evidence=[],
                recommended_action="pip install non_existent_pkg_xyz",
                severity="error",
                verification_status="unverified",
                source="gemma",
                category="missing_dependency",
                failure_status="failed",
                fallback_used=True,
                fallback_summary="Missing Python module: 'non_existent_pkg_xyz'",
                detail="evidence_not_in_log",
            )

        gemma_analysis.analyze_failure_logs = fake_analyze
        try:
            record = run_process(
                [sys.executable, "-c", "import non_existent_pkg_xyz"],
                heartbeat_interval=0.5,
                job_id="gemmarun",
            )
        finally:
            gemma_analysis.analyze_failure_logs = original
            if previous is None:
                os.environ.pop("GEMMA_ENABLED", None)
            else:
                os.environ["GEMMA_ENABLED"] = previous
        failed = record.events[-1]
        validate_message(failed)
        self.assertEqual(failed["explanation"]["verification_status"], "unverified")
        self.assertEqual(failed["explanation"]["category"], "missing_dependency")
        self.assertNotEqual(failed["explanation"]["verification_status"], "verified")


class RelayCardTests(unittest.TestCase):
    def test_relay_exposes_gemma_card_fields(self) -> None:
        result = analyze_failure_logs(
            _connection_log(),
            client=_ScriptedClient(_gemma_json(REAL_LINE)),
        )
        relay = TelemetryRelay("http://127.0.0.1:8090", "test-token")

        def fetch(path: str) -> dict:
            if path == "/v1/lights":
                return {"state": "failed", "code": 4, "job_id": "job-gemma", "progress": 10}
            if path == "/v1/jobs/job-gemma":
                return {
                    "excerpt": REAL_LINE,
                    "explanation": result.to_explanation_dict(),
                    "latest": {
                        "event": "failed",
                        "progress": 10,
                        "exit_code": 1,
                        "is_failure": True,
                        "message": "Process exited with code 1",
                    },
                }
            return {}

        relay._fetch_endpoint = fetch  # type: ignore[method-assign]
        job = relay.get_snapshot()["job"]
        self.assertEqual(job["explanation"]["verification_status"], "verified")
        self.assertEqual(job["explanation"]["evidence"][0]["log_line"], REAL_LINE)
        self.assertNotEqual(job["explanation"]["diagnosis"], job["explanation"]["evidence"][0]["log_line"])


if __name__ == "__main__":
    unittest.main()
