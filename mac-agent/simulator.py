"""Deterministic job scenarios for the Still Loading... Mac simulator.

Heartbeats, progress updates, and the final outcome are separate signals:

- A heartbeat means the monitor is still sending a liveness signal.
- A progress update means the scenario reported a new percent complete.
- ``failed`` is the only event that declares a job failure.
- ``heartbeat_paused`` means the scenario stopped heartbeats on purpose.
  The job is still treated as running.

The clock is injected so tests can run a 20 second scenario instantly.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

SCHEMA_VERSION = 1

# These names are the only modes the command-line tool accepts.
MODES = ("normal", "slow", "hang", "fail")

LIFECYCLE_EVENTS = frozenset(
    {
        "started",
        "heartbeat",
        "progress",
        "heartbeat_paused",
        "failed",
        "completed",
        "scenario_ended",
    }
)


@dataclass(frozen=True)
class Scenario:
    """Timing for one simulated job, measured in scenario seconds."""

    duration: float
    heartbeat_interval: float
    progress_interval: float
    tick: float = 0.25
    fail_at: float | None = None
    pause_heartbeats_at: float | None = None
    # ``completed`` claims success. ``scenario_ended`` stops without a verdict.
    ends_with: str = "completed"


# Shared demo clock. A real 20 second wait is long enough to watch, and
# short enough to rerun. ``--fast`` prints the same script without waiting.
SCENARIOS = {
    "normal": Scenario(
        duration=20.0,
        heartbeat_interval=2.0,
        progress_interval=3.0,
    ),
    "slow": Scenario(
        duration=20.0,
        heartbeat_interval=2.0,
        progress_interval=8.0,
    ),
    "hang": Scenario(
        duration=20.0,
        heartbeat_interval=2.0,
        progress_interval=3.0,
        pause_heartbeats_at=8.0,
        ends_with="scenario_ended",
    ),
    "fail": Scenario(
        duration=20.0,
        heartbeat_interval=2.0,
        progress_interval=3.0,
        fail_at=10.0,
    ),
}


class SystemClock:
    """Wall clock used by the live command-line run."""

    def __init__(self) -> None:
        self._elapsed = 0.0
        self._mono_origin = time.monotonic()
        self._wall_origin = datetime.now(timezone.utc)

    def elapsed(self) -> float:
        return time.monotonic() - self._mono_origin

    def wall_time(self, elapsed_seconds: float) -> datetime:
        return self._wall_origin + timedelta(seconds=elapsed_seconds)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class ManualClock:
    """Clock that moves only when ``sleep`` is called.

    Tests use a fixed start time so the JSON timestamps stay stable.
    ``--fast`` uses the current time and still skips the real wait.
    """

    def __init__(self, wall_origin: datetime | None = None) -> None:
        self._elapsed = 0.0
        if wall_origin is None:
            wall_origin = datetime(2026, 1, 1, tzinfo=timezone.utc)
        if wall_origin.tzinfo is None:
            raise ValueError("wall_origin must include a timezone")
        self._wall_origin = wall_origin.astimezone(timezone.utc)

    def elapsed(self) -> float:
        return self._elapsed

    def wall_time(self, elapsed_seconds: float) -> datetime:
        return self._wall_origin + timedelta(seconds=elapsed_seconds)

    def sleep(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("sleep seconds must be >= 0")
        self._elapsed += seconds


def new_job_id() -> str:
    """Return a short id that is easy to read in the terminal."""
    return uuid.uuid4().hex[:8]


def format_timestamp(moment: datetime) -> str:
    """Format UTC time as ``2026-01-01T00:00:02.000Z``."""
    utc = moment.astimezone(timezone.utc)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def validate_event(event: dict) -> None:
    """Raise ``ValueError`` when an event is missing a required field."""
    required = (
        "schema_version",
        "event",
        "job_id",
        "sequence",
        "timestamp",
        "elapsed_seconds",
        "mode",
        "progress",
        "is_failure",
    )
    missing = [key for key in required if key not in event]
    if missing:
        raise ValueError(f"event is missing {missing}")

    if event["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unexpected schema_version")
    if event["event"] not in LIFECYCLE_EVENTS:
        raise ValueError(f"unknown event type {event['event']!r}")
    if not isinstance(event["job_id"], str) or not event["job_id"]:
        raise ValueError("job_id must be a non-empty string")
    if not isinstance(event["sequence"], int) or event["sequence"] < 1:
        raise ValueError("sequence must be a positive integer")
    if not isinstance(event["elapsed_seconds"], (int, float)):
        raise ValueError("elapsed_seconds must be a number")
    if event["elapsed_seconds"] < 0:
        raise ValueError("elapsed_seconds must be >= 0")
    if event["mode"] not in SCENARIOS:
        raise ValueError(f"unknown mode {event['mode']!r}")

    timestamp = event["timestamp"]
    if (
        not isinstance(timestamp, str)
        or len(timestamp) != 24
        or not timestamp.endswith("Z")
        or timestamp[10] != "T"
    ):
        raise ValueError("timestamp must look like 2026-01-01T00:00:00.000Z")

    progress = event["progress"]
    if not isinstance(progress, int) or not 0 <= progress <= 100:
        raise ValueError("progress must be an integer from 0 to 100")

    if event["event"] == "failed":
        if event["is_failure"] is not True:
            raise ValueError("failed events must set is_failure true")
        if event.get("exit_code") != 1:
            raise ValueError("failed events must include exit_code 1")
        if not event.get("message"):
            raise ValueError("failed events must include a message")
    elif event["is_failure"] is not False:
        raise ValueError("only failed events may set is_failure true")

    if event["event"] == "completed":
        if event["progress"] != 100:
            raise ValueError("completed events must report progress 100")
        if event.get("exit_code") != 0:
            raise ValueError("completed events must include exit_code 0")

    if event["event"] == "heartbeat_paused":
        if event.get("reason") != "simulated_missing_heartbeat":
            raise ValueError("heartbeat_paused needs the simulated_missing_heartbeat reason")

    if event["event"] == "scenario_ended":
        if event.get("outcome") != "missing_heartbeat":
            raise ValueError("scenario_ended must record outcome missing_heartbeat")


def _build_event(
    *,
    event: str,
    job_id: str,
    sequence: int,
    mode: str,
    elapsed_seconds: float,
    timestamp: str,
    progress: int,
    is_failure: bool,
    extra: dict,
) -> dict:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "event": event,
        "job_id": job_id,
        "sequence": sequence,
        "timestamp": timestamp,
        "elapsed_seconds": elapsed_seconds,
        "mode": mode,
        "progress": progress,
        "is_failure": is_failure,
    }
    payload.update(extra)
    validate_event(payload)
    return payload


def run_scenario(mode: str, job_id: str, clock, emit) -> None:
    """Run one scenario and pass each event dict to ``emit``."""
    if mode not in SCENARIOS:
        raise ValueError(f"unknown mode {mode!r}; choose from {', '.join(MODES)}")
    if not job_id:
        raise ValueError("job_id must be a non-empty string")

    scenario = SCENARIOS[mode]
    if scenario.tick <= 0:
        raise ValueError("tick must be > 0")

    origin = clock.elapsed()
    sequence = 0
    last_heartbeat = 0.0
    last_progress = 0.0
    progress = 0
    heartbeats_paused = False
    pause_announced = False
    # Event times follow this scenario clock. A real sleep may wake a few
    # milliseconds late; the next wait is shortened so the script stays put.
    logical_elapsed = 0.0

    def send(event: str, *, is_failure: bool, extra: dict | None = None) -> None:
        nonlocal sequence
        sequence += 1
        payload = _build_event(
            event=event,
            job_id=job_id,
            sequence=sequence,
            mode=mode,
            elapsed_seconds=logical_elapsed,
            timestamp=format_timestamp(clock.wall_time(logical_elapsed)),
            progress=progress,
            is_failure=is_failure,
            extra=extra or {},
        )
        emit(payload)

    send("started", is_failure=False)

    max_steps = int(scenario.duration / scenario.tick) + 2
    for step in range(max_steps + 1):
        logical_elapsed = round(step * scenario.tick, 3)
        delay = (origin + logical_elapsed) - clock.elapsed()
        if delay > 0:
            clock.sleep(delay)
        elapsed = logical_elapsed

        # An explicit failure wins over any heartbeat due at the same moment.
        if scenario.fail_at is not None and elapsed >= scenario.fail_at:
            send(
                "failed",
                is_failure=True,
                extra={
                    "message": "Simulated build error",
                    "exit_code": 1,
                },
            )
            return

        if (
            scenario.pause_heartbeats_at is not None
            and elapsed >= scenario.pause_heartbeats_at
            and not pause_announced
        ):
            heartbeats_paused = True
            pause_announced = True
            send(
                "heartbeat_paused",
                is_failure=False,
                extra={
                    "reason": "simulated_missing_heartbeat",
                    "message": (
                        "Heartbeats stopped on purpose. The job has not failed."
                    ),
                },
            )

        if elapsed >= scenario.duration:
            if scenario.ends_with == "completed":
                progress = 100
                send("completed", is_failure=False, extra={"exit_code": 0})
            else:
                send(
                    "scenario_ended",
                    is_failure=False,
                    extra={
                        "outcome": "missing_heartbeat",
                        "message": (
                            "Scenario finished. Heartbeats were missing. "
                            "No failure was declared."
                        ),
                    },
                )
            return

        if (
            not heartbeats_paused
            and elapsed > 0
            and elapsed - last_heartbeat >= scenario.heartbeat_interval
        ):
            last_heartbeat = elapsed
            send("heartbeat", is_failure=False)

        if elapsed > 0 and elapsed - last_progress >= scenario.progress_interval:
            last_progress = elapsed
            progress = min(99, int(elapsed / scenario.duration * 100))
            send("progress", is_failure=False)

    raise RuntimeError(f"scenario {mode!r} did not finish")


def collect_events(
    mode: str,
    job_id: str = "job-test",
    clock: ManualClock | None = None,
) -> list[dict]:
    """Run a scenario on a manual clock and return every event."""
    events: list[dict] = []
    run_scenario(mode, job_id, clock or ManualClock(), events.append)
    return events
