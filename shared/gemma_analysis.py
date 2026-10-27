"""Gemma failure analysis with a code-level evidence check.

A diagnosis is verified only when every cited log line is a contiguous fragment
of the redacted log that was sent to the model. A plausible sentence with no
matching citation stays ``unverified``. Timeouts, unreachable endpoints, and
malformed JSON fall back to the rules explainer and never claim verification.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from excerpt import redact
from explainer import explain_failure
from gemma_client import GemmaClient, GemmaConfig, GemmaTimeout, GemmaUnavailable

logger = logging.getLogger("still_loading.gemma")

SEVERITIES = ("info", "warning", "error", "critical")
MIN_CITATION_CHARS = 8

_EXTRA_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{8,}"), "[REDACTED]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED]"),
    (re.compile(r"(?i)\b(x-api-key\s*[:=]\s*)\S+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)([a-z][a-z0-9+.-]*://)[^/\s@]+(?::[^/\s@]*)?@"), r"\1[REDACTED]@"),
]


class GemmaMalformedOutput(ValueError):
    """The model text was not the required JSON object."""


@dataclass(frozen=True)
class EvidenceItem:
    log_line: str
    reason: str
    found: bool


@dataclass
class AnalysisResult:
    diagnosis: str
    confidence: float
    evidence: list[EvidenceItem]
    recommended_action: str
    severity: str
    verification_status: str
    source: str
    category: str
    failure_status: str = "failed"
    fallback_used: bool = False
    fallback_summary: str = ""
    detail: str = ""
    rules_suggestion: str = ""

    def to_explanation_dict(self) -> dict:
        """Shape stored on a failed wire event and in job history."""
        payload = {
            "category": (self.category or "generic_error")[:64],
            "summary": (self.diagnosis or "Failure recorded")[:256],
            "suggestion": (self.recommended_action or "")[:512],
            "confidence": _clamp_confidence(self.confidence),
            "source": self.source,
            "severity": self.severity if self.severity in SEVERITIES else "error",
            "verification_status": self.verification_status,
            "diagnosis": (self.diagnosis or "")[:256],
            "recommended_action": (self.recommended_action or "")[:512],
            "evidence": [
                {
                    "log_line": item.log_line[:180],
                    "reason": item.reason[:160],
                    "found": bool(item.found),
                }
                for item in self.evidence[:4]
            ],
        }
        if self.fallback_summary:
            payload["fallback_summary"] = self.fallback_summary[:256]
        if self.detail:
            payload["detail"] = self.detail[:120]
        return payload

    def to_ui_card(self) -> dict:
        labels = {
            "verified": "Evidence verified",
            "unverified": "Evidence unverified",
            "unavailable": "Gemma unavailable",
            "timeout": "Gemma timed out",
            "malformed": "Malformed model response",
        }
        return {
            "title": "Gemma Failure Analysis",
            "failure_status": self.failure_status,
            "diagnosis": self.diagnosis,
            "confidence": _clamp_confidence(self.confidence),
            "confidence_label": f"{round(_clamp_confidence(self.confidence) * 100)}%",
            "severity": self.severity if self.severity in SEVERITIES else "error",
            "evidence": [
                {"log_line": item.log_line, "reason": item.reason, "found": item.found}
                for item in self.evidence
            ],
            "recommended_action": self.recommended_action,
            "verification_status": self.verification_status,
            "verification_label": labels.get(self.verification_status, "Evidence unverified"),
            "fallback_used": self.fallback_used,
            "fallback_summary": self.fallback_summary,
            "source": self.source,
            "verified": self.verification_status == "verified",
        }

    def compact_board_status(self) -> dict:
        """Light-weight status. The matrix keeps its existing state codes."""
        return {
            "board_state": self.failure_status,
            "gemma_verification": self.verification_status,
            "renders_diagnosis_on_matrix": False,
        }


@dataclass
class _Parsed:
    diagnosis: str
    confidence: float
    evidence: list[tuple[str, str]] = field(default_factory=list)
    recommended_action: str = ""
    severity: str = "error"


def redact_for_model(text: str) -> str:
    """Remove secrets before any log text is placed in a model prompt."""
    cleaned = redact(text or "")
    for pattern, replacement in _EXTRA_SECRET_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned


def limit_log(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n[truncated]"


def parse_gemma_output(text: str) -> _Parsed:
    payload = _load_json_object(text)
    diagnosis = payload.get("diagnosis")
    if not isinstance(diagnosis, str) or not diagnosis.strip():
        raise GemmaMalformedOutput("diagnosis must be a non-empty string")
    confidence = payload.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise GemmaMalformedOutput("confidence must be a number")
    action = payload.get("recommended_action")
    if not isinstance(action, str):
        raise GemmaMalformedOutput("recommended_action must be a string")
    severity = payload.get("severity")
    if severity not in SEVERITIES:
        raise GemmaMalformedOutput("severity is not a supported value")
    raw_evidence = payload.get("evidence")
    if not isinstance(raw_evidence, list):
        raise GemmaMalformedOutput("evidence must be a list")
    evidence: list[tuple[str, str]] = []
    for item in raw_evidence:
        if not isinstance(item, dict):
            raise GemmaMalformedOutput("evidence items must be objects")
        line = item.get("log_line")
        reason = item.get("reason", "")
        if not isinstance(line, str) or not isinstance(reason, str):
            raise GemmaMalformedOutput("evidence log_line and reason must be strings")
        evidence.append((line.strip(), reason.strip()))
    return _Parsed(
        diagnosis=diagnosis.strip(),
        confidence=float(confidence),
        evidence=evidence,
        recommended_action=action.strip(),
        severity=severity,
    )


def citation_found(citation: str, source: str) -> bool:
    """True when the citation is a contiguous fragment of the source log."""
    needle = " ".join(citation.split())
    haystack = " ".join((source or "").split())
    if len(needle) < MIN_CITATION_CHARS:
        return False
    return needle in haystack


def validate_evidence(parsed: _Parsed, source_log: str) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            log_line=line,
            reason=reason,
            found=citation_found(line, source_log),
        )
        for line, reason in parsed.evidence
    ]


def analyze_failure_logs(
    logs: str,
    *,
    exit_code: int = 1,
    message: str = "",
    failure_status: str = "failed",
    client: GemmaClient | None = None,
    config: GemmaConfig | None = None,
) -> AnalysisResult:
    """Redact logs, ask Gemma when configured, and verify every citation."""
    if config is not None:
        cfg = config
    elif client is not None and getattr(client, "config", None) is not None:
        cfg = client.config
    else:
        cfg = GemmaConfig.from_env()
    redacted = limit_log(redact_for_model(logs), cfg.max_log_chars)
    rules = explain_failure(exit_code=exit_code, message=message, excerpt=redacted or None)
    rules_result = _from_rules(
        rules,
        failure_status=failure_status,
        verification_status="unavailable",
        detail="rules",
        fallback_used=False,
    )

    if not redacted.strip():
        logger.info("gemma skipped empty_logs")
        return _from_rules(
            rules,
            failure_status=failure_status,
            verification_status="unavailable",
            detail="empty_logs",
            fallback_used=True,
        )

    if client is None:
        if not cfg.enabled:
            return rules_result
        client = GemmaClient(cfg)

    prompt = _prompt(redacted, exit_code=exit_code, message=message)
    try:
        raw = client.complete(prompt)
    except GemmaTimeout:
        logger.info("gemma result status=timeout")
        return _from_rules(
            rules,
            failure_status=failure_status,
            verification_status="timeout",
            detail="timeout",
            fallback_used=True,
        )
    except GemmaUnavailable as exc:
        logger.info("gemma result status=unavailable reason=%s", exc)
        return _from_rules(
            rules,
            failure_status=failure_status,
            verification_status="unavailable",
            detail="unavailable",
            fallback_used=True,
        )
    except Exception:
        logger.exception("gemma client failed closed")
        return _from_rules(
            rules,
            failure_status=failure_status,
            verification_status="unavailable",
            detail="unavailable",
            fallback_used=True,
        )

    try:
        parsed = parse_gemma_output(raw)
    except GemmaMalformedOutput:
        logger.info("gemma result status=malformed")
        return _from_rules(
            rules,
            failure_status=failure_status,
            verification_status="malformed",
            detail="malformed",
            fallback_used=True,
        )

    evidence = validate_evidence(parsed, redacted)
    verified = bool(evidence) and all(item.found for item in evidence)
    if not verified:
        logger.info(
            "gemma result status=unverified citations=%s matched=%s",
            len(evidence),
            sum(1 for item in evidence if item.found),
        )
        return AnalysisResult(
            diagnosis=parsed.diagnosis,
            confidence=_clamp_confidence(parsed.confidence),
            evidence=evidence,
            recommended_action=parsed.recommended_action,
            severity=parsed.severity,
            verification_status="unverified",
            source="gemma",
            category=rules.category,
            failure_status=failure_status,
            fallback_used=True,
            fallback_summary=rules.summary,
            detail="evidence_not_in_log",
            rules_suggestion=rules.suggestion,
        )

    logger.info("gemma result status=verified citations=%s", len(evidence))
    return AnalysisResult(
        diagnosis=parsed.diagnosis,
        confidence=_clamp_confidence(parsed.confidence),
        evidence=evidence,
        recommended_action=parsed.recommended_action,
        severity=parsed.severity,
        verification_status="verified",
        source="gemma",
        category=rules.category,
        failure_status=failure_status,
        fallback_used=False,
        fallback_summary="",
        detail="evidence_matched",
        rules_suggestion=rules.suggestion,
    )


def _from_rules(rules, *, failure_status: str, verification_status: str, detail: str, fallback_used: bool) -> AnalysisResult:
    return AnalysisResult(
        diagnosis=rules.summary,
        confidence=rules.confidence,
        evidence=[],
        recommended_action=rules.suggestion,
        severity="error" if rules.category not in {"interrupted"} else "warning",
        verification_status=verification_status,
        source="fallback" if fallback_used else rules.source,
        category=rules.category,
        failure_status=failure_status,
        fallback_used=fallback_used,
        fallback_summary=rules.summary if fallback_used else "",
        detail=detail,
        rules_suggestion=rules.suggestion,
    )


def _prompt(log_text: str, *, exit_code: int, message: str) -> str:
    note = redact_for_model(message or "")
    return (
        f"Exit code: {exit_code}\n"
        f"Runner message: {note}\n"
        "Log:\n"
        "----- LOG START -----\n"
        f"{log_text}\n"
        "----- LOG END -----\n"
        "Cite log_line values only from between the markers."
    )


def _load_json_object(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise GemmaMalformedOutput("response is not JSON") from None
        try:
            value = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise GemmaMalformedOutput("response is not JSON") from exc
    if not isinstance(value, dict):
        raise GemmaMalformedOutput("response JSON must be an object")
    return value


def _clamp_confidence(value: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number < 0:
        return 0.0
    if number > 1:
        return 1.0
    return number
