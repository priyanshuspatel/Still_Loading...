"""Turn accepted job events into one light state.

``apply`` and ``tick`` use the clock the caller passes in. On the board that
clock is the receiver's monotonic clock. The Mac event timestamp is stored
with the message and is not used to decide a stall, because the two machines
do not share a clock.

A gap with no heartbeat becomes ``suspected_stall``. It does not become
``failed``. Only an accepted ``failed`` event does that.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from messages import ProtocolError, validate_message

STATES = (
    "idle",
    "running",
    "slow",
    "suspected_stall",
    "failed",
    "completed",
)
TERMINAL = frozenset({"failed", "completed"})
ALIVE = frozenset({"running", "slow"})

# Integers the microcontroller sketch understands. Keep this table in sync
# with uno-q/sketch/sketch.ino.
STATE_CODE = {
    "idle": 0,
    "running": 1,
    "slow": 2,
    "suspected_stall": 3,
    "failed": 4,
    "completed": 5,
}


@dataclass(frozen=True)
class EngineConfig:
    """Seconds on the receiver clock."""

    heartbeat_timeout_s: float = 6.0
    slow_progress_gap_s: float = 6.0


@dataclass(frozen=True)
class LightView:
    state: str
    job_id: str | None
    progress: int
    sequence: int
    reason: str

    @property
    def code(self) -> int:
        return STATE_CODE[self.state]


@dataclass
class _Job:
    state: str = "idle"
    last_sequence: int = 0
    last_heartbeat_at: float | None = None
    last_progress_at: float | None = None
    progress: int = 0


class StateEngine:
    """The most recently accepted job is the one the lights follow."""

    def __init__(self, config: EngineConfig | None = None, on_change=None) -> None:
        self.config = config or EngineConfig()
        self._on_change = on_change
        self._lock = threading.Lock()
        self._jobs: dict[str, _Job] = {}
        self._focus: str | None = None
        self._view = LightView("idle", None, 0, 0, "startup")

    @property
    def view(self) -> LightView:
        with self._lock:
            return self._view

    def apply(self, event: dict, now: float) -> LightView:
        """Record one event. Invalid, duplicate, and stale events do not move the lights."""
        try:
            checked = validate_message(event)
        except ProtocolError:
            return self.view

        notify: LightView | None = None
        with self._lock:
            job_id = checked["job_id"]
            sequence = checked["sequence"]
            name = checked["event"]
            job = self._jobs.setdefault(job_id, _Job())
            if sequence <= job.last_sequence or job.state in TERMINAL:
                return self._view

            job.last_sequence = sequence
            job.progress = checked["progress"]
            self._focus = job_id

            if name == "started":
                job.state = "running"
                job.last_heartbeat_at = now
                job.last_progress_at = None
                reason = "started"
            elif name == "heartbeat":
                job.last_heartbeat_at = now
                if job.state in {"suspected_stall", "idle"}:
                    job.state = "running"
                reason = "heartbeat"
            elif name == "progress":
                gap = None if job.last_progress_at is None else now - job.last_progress_at
                if gap is not None and gap >= self.config.slow_progress_gap_s and job.state in ALIVE:
                    job.state = "slow"
                elif job.state == "slow":
                    job.state = "running"
                elif job.state == "idle":
                    job.state = "running"
                    job.last_heartbeat_at = now
                job.last_progress_at = now
                reason = "progress"
            elif name == "failed":
                job.state = "failed"
                reason = "failed"
            else:
                job.state = "completed"
                job.progress = 100
                reason = "completed"

            notify = self._stage(reason)
        if notify is not None and self._on_change is not None:
            self._on_change(notify)
        return self.view

    def tick(self, now: float) -> LightView:
        """Mark a missing heartbeat. This returns immediately."""
        notify: LightView | None = None
        with self._lock:
            if self._focus is None:
                return self._view
            job = self._jobs[self._focus]
            if job.state not in ALIVE or job.last_heartbeat_at is None:
                return self._view
            if now - job.last_heartbeat_at < self.config.heartbeat_timeout_s:
                return self._view
            job.state = "suspected_stall"
            notify = self._stage("heartbeat_timeout")
        if notify is not None and self._on_change is not None:
            self._on_change(notify)
        return self.view

    def _stage(self, reason: str) -> LightView | None:
        job_id = self._focus
        job = self._jobs[job_id] if job_id else None
        view = LightView(
            state=job.state if job else "idle",
            job_id=job_id,
            progress=job.progress if job else 0,
            sequence=job.last_sequence if job else 0,
            reason=reason,
        )
        changed = (
            view.state != self._view.state
            or view.progress != self._view.progress
            or view.job_id != self._view.job_id
        )
        self._view = view
        return view if changed else None
