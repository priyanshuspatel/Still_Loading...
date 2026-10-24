"""Validate Still Loading... job messages and remember sequence numbers.

This file is the shared rule book for the Mac and the UNO Q. It does not
open a socket and it does not decide LED colors.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

SCHEMA_VERSION = 1
MAX_BODY_BYTES = 8192
MIN_TOKEN_LENGTH = 16

# Events the board is willing to store.
WIRE_EVENTS = frozenset(
    {"started", "heartbeat", "progress", "failed", "completed"}
)

# Printed by the simulator so a person can see what happened. They describe
# the pretend run. They are not job results, so the sender leaves them local.
SIMULATOR_ONLY_EVENTS = frozenset({"heartbeat_paused", "scenario_ended"})

REQUIRED_FIELDS = (
    "schema_version",
    "event",
    "job_id",
    "sequence",
    "timestamp",
    "elapsed_seconds",
    "progress",
    "is_failure",
)

OPTIONAL_FIELDS = frozenset({"mode", "source"})
TERMINAL_EVENTS = frozenset({"failed", "completed"})
_JOB_ID_EXTRA = frozenset("-_")


class ProtocolError(Exception):
    """A message or request the receiver can answer with an HTTP status."""

    def __init__(self, status: int, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.reason = reason
        self.detail = detail


def load_local_config(path: Path) -> dict:
    """Read a local JSON config. The file should stay off git."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ProtocolError(0, "missing_config", f"Config file not found: {path}")
    except json.JSONDecodeError as exc:
        raise ProtocolError(0, "bad_config", f"Config file is not valid JSON: {exc}")
    if not isinstance(data, dict):
        raise ProtocolError(0, "bad_config", "Config file must contain a JSON object")
    return data


def token_is_long_enough(token: str) -> bool:
    return isinstance(token, str) and len(token.strip()) >= MIN_TOKEN_LENGTH


def parse_json_object(raw: bytes) -> dict:
    """Turn a request body into a dict, or raise ProtocolError(400)."""
    if len(raw) > MAX_BODY_BYTES:
        raise ProtocolError(400, "body_too_large", "Message is larger than 8192 bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ProtocolError(400, "not_utf8", "Message must be UTF-8 JSON")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        raise ProtocolError(400, "malformed_json", "Message is not valid JSON")
    if not isinstance(value, dict):
        raise ProtocolError(400, "not_an_object", "Message must be a JSON object")
    return value


def _reject(reason: str, detail: str) -> None:
    raise ProtocolError(400, reason, detail)


def _require_bool(value: object, field: str) -> None:
    # bool is a subclass of int, so callers check it on its own.
    if not isinstance(value, bool):
        _reject("invalid_field", f"{field} must be true or false")


def _require_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _reject("invalid_field", f"{field} must be an integer")
    return value


def validate_message(message: dict) -> dict:
    """Return the message when it matches schema version 1.

    Sequence order is checked later, per job, by ``JobLog``.
    """
    if not isinstance(message, dict):
        _reject("not_an_object", "Message must be a JSON object")

    missing = [field for field in REQUIRED_FIELDS if field not in message]
    if missing:
        _reject("missing_field", "Message is missing " + ", ".join(missing))

    allowed = set(REQUIRED_FIELDS) | OPTIONAL_FIELDS | {"message", "exit_code"}
    unknown = sorted(set(message) - allowed)
    if unknown:
        _reject("unknown_field", "Message has unknown fields: " + ", ".join(unknown))

    if message["schema_version"] != SCHEMA_VERSION:
        _reject("bad_schema_version", "schema_version must be 1")

    event = message["event"]
    if not isinstance(event, str) or event not in WIRE_EVENTS:
        _reject("unknown_event", f"Unknown event type: {event!r}")

    job_id = message["job_id"]
    if (
        not isinstance(job_id, str)
        or not job_id
        or len(job_id) > 64
        or any(not (character.isalnum() or character in _JOB_ID_EXTRA) for character in job_id)
    ):
        _reject(
            "invalid_field",
            "job_id must be 1-64 characters and use letters, numbers, _ or -",
        )

    sequence = _require_int(message["sequence"], "sequence")
    if sequence < 1:
        _reject("invalid_field", "sequence must be 1 or greater")

    timestamp = message["timestamp"]
    if (
        not isinstance(timestamp, str)
        or len(timestamp) != 24
        or timestamp[10] != "T"
        or not timestamp.endswith("Z")
    ):
        _reject("invalid_field", "timestamp must look like 2026-01-01T00:00:00.000Z")

    elapsed = message["elapsed_seconds"]
    if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)):
        _reject("invalid_field", "elapsed_seconds must be a number")
    if elapsed < 0:
        _reject("invalid_field", "elapsed_seconds must be 0 or greater")

    progress = _require_int(message["progress"], "progress")
    if not 0 <= progress <= 100:
        _reject("invalid_field", "progress must be from 0 to 100")

    _require_bool(message["is_failure"], "is_failure")

    if "mode" in message:
        mode = message["mode"]
        if not isinstance(mode, str) or not mode or len(mode) > 32:
            _reject("invalid_field", "mode must be a short string when it is present")
    if "source" in message:
        source = message["source"]
        if not isinstance(source, str) or not source or len(source) > 32:
            _reject("invalid_field", "source must be a short string when it is present")

    if event == "failed":
        if message["is_failure"] is not True:
            _reject("invalid_field", "failed events must set is_failure to true")
        message_text = message.get("message")
        if not isinstance(message_text, str) or not message_text.strip():
            _reject("invalid_field", "failed events must include a message")
        if len(message_text) > 500:
            _reject("invalid_field", "failed message must be 500 characters or fewer")
        exit_code = _require_int(message.get("exit_code"), "exit_code")
        if exit_code == 0:
            _reject("invalid_field", "failed events must use a non-zero exit_code")
    elif event == "completed":
        if message["is_failure"] is not False:
            _reject("invalid_field", "completed events must set is_failure to false")
        if progress != 100:
            _reject("invalid_field", "completed events must report progress 100")
        if _require_int(message.get("exit_code"), "exit_code") != 0:
            _reject("invalid_field", "completed events must use exit_code 0")
        if "message" in message:
            _reject("unknown_field", "completed events do not take a message")
    else:
        if message["is_failure"] is not False:
            _reject("invalid_field", "only failed events may set is_failure to true")
        if "message" in message or "exit_code" in message:
            _reject("unknown_field", f"{event} events do not take message or exit_code")

    return message


class JobLog:
    """In-memory list of accepted messages, keyed by job id.

    A lost network connection never reaches this object, so it cannot turn
    into a stored failure.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._highest: dict[str, int] = {}
        self._closed: set[str] = set()
        self._events: dict[str, list[dict]] = {}

    def accept(self, message: dict) -> dict:
        """Validate and store one message. Raise ProtocolError when it is refused."""
        checked = validate_message(message)
        job_id = checked["job_id"]
        sequence = checked["sequence"]
        with self._lock:
            highest = self._highest.get(job_id, 0)
            if job_id in self._closed and sequence > highest:
                raise ProtocolError(
                    409,
                    "terminal",
                    "This job already has a completed or failed event",
                )
            if sequence == highest and highest != 0:
                raise ProtocolError(
                    409,
                    "duplicate",
                    f"Sequence {sequence} was already accepted for this job",
                )
            if sequence < highest:
                raise ProtocolError(
                    409,
                    "stale",
                    f"Sequence {sequence} is older than {highest}",
                )
            self._highest[job_id] = sequence
            self._events.setdefault(job_id, []).append(checked)
            if checked["event"] in TERMINAL_EVENTS:
                self._closed.add(job_id)
        return checked

    def events(self, job_id: str) -> list[dict]:
        with self._lock:
            return list(self._events.get(job_id, []))

    def latest(self, job_id: str) -> dict | None:
        with self._lock:
            found = self._events.get(job_id)
            if not found:
                return None
            return found[-1]

    def snapshot(self, job_id: str) -> dict | None:
        """A small read-back record. It contains no token and no other jobs."""
        with self._lock:
            found = self._events.get(job_id)
            if not found:
                return None
            return {
                "job_id": job_id,
                "accepted_count": len(found),
                "highest_sequence": self._highest[job_id],
                "latest": found[-1],
            }
