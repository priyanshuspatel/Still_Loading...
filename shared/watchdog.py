"""Mac-side failure and stall watchdog.

The state engine still decides ``suspected_stall`` and ``failed`` on its own
clock. Gemma runs only after that decision, on a daemon thread, and only until
``timeout_s``. If the model is slow or down, ``tick`` and ``apply`` still
return the light state the engine already chose.
"""

from __future__ import annotations

import threading
from typing import Callable

from explainer import explain_failure
from gemma_analysis import AnalysisResult, analyze_failure_logs
from gemma_client import GemmaClient, GemmaConfig
from state_engine import StateEngine


class FailureWatchdog:
    def __init__(
        self,
        engine: StateEngine,
        *,
        client: GemmaClient | None = None,
        config: GemmaConfig | None = None,
        timeout_s: float = 8.0,
        analyzer: Callable[..., AnalysisResult] | None = None,
    ) -> None:
        self.engine = engine
        self.client = client
        self.config = config
        self.timeout_s = max(0.05, timeout_s)
        self._analyzer = analyzer or analyze_failure_logs
        self._logs: dict[str, str] = {}
        self.latest: AnalysisResult | None = None

    def remember_logs(self, job_id: str, logs: str) -> None:
        self._logs[job_id] = logs

    def apply(self, event: dict, now: float):
        view = self.engine.apply(event, now)
        if view.reason == "failed" and view.job_id:
            logs = self._logs.get(view.job_id) or str(event.get("excerpt") or "")
            self.latest = self._analyze_bounded(
                logs=logs,
                exit_code=int(event.get("exit_code") or 1),
                message=str(event.get("message") or ""),
                failure_status="failed",
            )
        return view

    def tick(self, now: float):
        previous = self.engine.view.state
        view = self.engine.tick(now)
        if view.state == "suspected_stall" and previous != "suspected_stall" and view.job_id:
            logs = self._logs.get(view.job_id, "")
            self.latest = self._analyze_bounded(
                logs=logs,
                exit_code=1,
                message="No heartbeat before the watchdog timeout",
                failure_status="suspected_stall",
            )
        return view

    def ui_payload(self) -> dict | None:
        if self.latest is None:
            return None
        return self.latest.to_ui_card()

    def _analyze_bounded(
        self,
        *,
        logs: str,
        exit_code: int,
        message: str,
        failure_status: str,
    ) -> AnalysisResult:
        box: dict = {}

        def target() -> None:
            try:
                box["value"] = self._analyzer(
                    logs,
                    exit_code=exit_code,
                    message=message,
                    failure_status=failure_status,
                    client=self.client,
                    config=self.config,
                )
            except Exception as exc:  # noqa: BLE001 - monitoring must continue
                box["error"] = exc

        worker = threading.Thread(target=target, name="gemma-watchdog", daemon=True)
        worker.start()
        worker.join(self.timeout_s)
        if worker.is_alive():
            return _rules_result(
                logs,
                exit_code=exit_code,
                message=message,
                failure_status=failure_status,
                verification_status="timeout",
                detail="watchdog_timeout",
            )
        value = box.get("value")
        if isinstance(value, AnalysisResult):
            return value
        return _rules_result(
            logs,
            exit_code=exit_code,
            message=message,
            failure_status=failure_status,
            verification_status="unavailable",
            detail="watchdog_error",
        )


def _rules_result(
    logs: str,
    *,
    exit_code: int,
    message: str,
    failure_status: str,
    verification_status: str,
    detail: str,
) -> AnalysisResult:
    rules = explain_failure(exit_code=exit_code, message=message, excerpt=logs or None)
    return AnalysisResult(
        diagnosis=rules.summary,
        confidence=rules.confidence,
        evidence=[],
        recommended_action=rules.suggestion,
        severity="warning" if rules.category == "interrupted" else "error",
        verification_status=verification_status,
        source="fallback",
        category=rules.category,
        failure_status=failure_status,
        fallback_used=True,
        fallback_summary=rules.summary,
        detail=detail,
        rules_suggestion=rules.suggestion,
    )
