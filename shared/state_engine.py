"""Turn accepted job events and optional battery readings into one light state.

``apply`` and ``tick`` use the clock the caller passes in. On the board that
clock is the receiver's monotonic clock. The Mac event timestamp is stored
with the message and is not used to decide a stall, because the two machines
do not share a clock.

A gap with no heartbeat becomes ``suspected_stall``. It does not become
``failed``. Only an accepted ``failed`` event does that.

Battery readings are stored separately from jobs. They never create or
modify a job in ``_jobs``, and active or failed jobs take priority unless
 the user explicitly selects ``battery`` display mode.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from messages import (
    DISPLAY_MODES,
    ProtocolError,
    validate_battery_message,
    validate_download_message,
    validate_message,
)

STATES = (
    "idle",
    "running",
    "slow",
    "suspected_stall",
    "failed",
    "completed",
    "battery",
    "battery_charging",
    "battery_unavailable",
    "download",
)
TERMINAL = frozenset({"failed", "completed"})
ALIVE = frozenset({"running", "slow"})
ACTIVE_OR_FAILED = frozenset({"running", "slow", "suspected_stall", "failed"})

# Integers the microcontroller sketch understands. Keep this table in sync
# with uno-q/sketch/sketch.ino and uno-q/app_lab_main.py.
STATE_CODE = {
    "idle": 0,
    "running": 1,
    "slow": 2,
    "suspected_stall": 3,
    "failed": 4,
    "completed": 5,
    "battery": 6,
    "battery_charging": 7,
    "battery_unavailable": 8,
    "download": 9,
}


@dataclass(frozen=True)
class EngineConfig:
    """Seconds on the receiver clock."""

    heartbeat_timeout_s: float = 6.0
    slow_progress_gap_s: float = 6.0
    display_mode: str = "auto"
    return_to_battery: bool = False
    download_complete_hold_s: float = 4.0
    download_failed_hold_s: float = 3.0


@dataclass(frozen=True)
class BatteryView:
    percent: int
    charging_state: str
    timestamp: str


@dataclass(frozen=True)
class DownloadView:
    download_id: str | None
    state: str
    progress: int
    progress_known: bool
    downloaded_bytes: int
    total_bytes: int | None
    timestamp: str
    updated_at: float
    hold_until: float | None = None
    filename: str | None = None


@dataclass(frozen=True)
class LightView:
    state: str
    job_id: str | None
    progress: int
    sequence: int
    reason: str
    progress_known: bool = False
    display_mode: str = "auto"
    charging_state: str | None = None

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
    progress_known: bool = False


class StateEngine:
    """The most recently accepted job is the one the lights follow by default."""

    def __init__(self, config: EngineConfig | None = None, on_change=None) -> None:
        self.config = config or EngineConfig()
        if self.config.display_mode not in DISPLAY_MODES:
            raise ValueError(f"Unknown display_mode: {self.config.display_mode!r}")
        self._on_change = on_change
        self._lock = threading.Lock()
        self._jobs: dict[str, _Job] = {}
        self._focus: str | None = None
        self._battery: BatteryView | None = None
        self._download: DownloadView | None = None
        self._display_mode: str = self.config.display_mode
        self._return_to_battery: bool = bool(self.config.return_to_battery)
        self._job_view = LightView("idle", None, 0, 0, "startup")
        self._view = self._compute_display_view("startup")

    @property
    def view(self) -> LightView:
        with self._lock:
            return self._view

    @property
    def job_view(self) -> LightView:
        """Underlying job state, unaffected by battery display mode."""
        with self._lock:
            return self._job_view

    @property
    def battery_view(self) -> BatteryView | None:
        with self._lock:
            return self._battery

    @property
    def download_view(self) -> DownloadView | None:
        with self._lock:
            return self._download

    @property
    def display_mode(self) -> str:
        with self._lock:
            return self._display_mode

    @property
    def return_to_battery(self) -> bool:
        with self._lock:
            return self._return_to_battery

    def set_display_mode(
        self,
        mode: str,
        *,
        return_to_battery: bool | None = None,
    ) -> LightView:
        """Select ``auto``, ``job``, or ``battery`` display priority."""
        if not isinstance(mode, str) or mode not in DISPLAY_MODES:
            raise ProtocolError(
                400,
                "invalid_field",
                "display_mode must be auto, job, or battery",
            )
        notify: LightView | None = None
        with self._lock:
            self._display_mode = mode
            if return_to_battery is not None:
                self._return_to_battery = bool(return_to_battery)
            notify = self._stage("display_mode")
        if notify is not None and self._on_change is not None:
            self._on_change(notify)
        return self.view

    def apply_battery(self, message: dict) -> LightView:
        """Record one validated Mac battery reading without touching any job."""
        checked = validate_battery_message(message)
        notify: LightView | None = None
        with self._lock:
            self._battery = BatteryView(
                percent=checked["percent"],
                charging_state=checked["charging_state"],
                timestamp=checked["timestamp"],
            )
            if "display_mode" in checked:
                self._display_mode = checked["display_mode"]
            if "return_to_battery" in checked:
                self._return_to_battery = bool(checked["return_to_battery"])
            notify = self._stage("battery")
        if notify is not None and self._on_change is not None:
            self._on_change(notify)
        return self.view

    def apply_download(self, message: dict, now: float | None = None) -> LightView:
        """Record one validated browser download reading without touching any job."""
        checked = validate_download_message(message)
        clock_now = time.monotonic() if now is None else float(now)
        state = checked["state"]
        notify: LightView | None = None
        with self._lock:
            if state == "idle":
                if (
                    self._download is not None
                    and self._download.hold_until is not None
                    and clock_now < self._download.hold_until
                ):
                    return self._view
                self._download = None
                notify = self._stage("download_idle")
            elif state == "cancelled":
                self._download = None
                notify = self._stage("download_cancelled")
            elif state == "completed":
                hold = (
                    clock_now + self.config.download_complete_hold_s
                    if self.config.download_complete_hold_s > 0
                    else None
                )
                self._download = DownloadView(
                    download_id=checked["download_id"],
                    state="completed",
                    progress=100,
                    progress_known=True,
                    downloaded_bytes=checked["downloaded_bytes"],
                    total_bytes=checked["total_bytes"],
                    timestamp=checked["timestamp"],
                    updated_at=clock_now,
                    hold_until=hold,
                    filename=checked.get("filename"),
                )
                notify = self._stage("download_completed")
            elif state == "failed":
                hold = (
                    clock_now + self.config.download_failed_hold_s
                    if self.config.download_failed_hold_s > 0
                    else None
                )
                self._download = DownloadView(
                    download_id=checked["download_id"],
                    state="failed",
                    progress=checked["progress"],
                    progress_known=checked["progress_known"],
                    downloaded_bytes=checked["downloaded_bytes"],
                    total_bytes=checked["total_bytes"],
                    timestamp=checked["timestamp"],
                    updated_at=clock_now,
                    hold_until=hold,
                    filename=checked.get("filename"),
                )
                notify = self._stage("download_failed")
            else:
                self._download = DownloadView(
                    download_id=checked["download_id"],
                    state=state,
                    progress=checked["progress"],
                    progress_known=checked["progress_known"],
                    downloaded_bytes=checked["downloaded_bytes"],
                    total_bytes=checked["total_bytes"],
                    timestamp=checked["timestamp"],
                    updated_at=clock_now,
                    hold_until=None,
                    filename=checked.get("filename"),
                )
                notify = self._stage("download")
        if notify is not None and self._on_change is not None:
            self._on_change(notify)
        return self.view

    def apply(self, event: dict, now: float) -> LightView:
        """Record one job event. Invalid, duplicate, and stale events do not move the lights."""
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
                job.progress_known = checked["progress"] > 0
                reason = "started"
            elif name == "heartbeat":
                job.last_heartbeat_at = now
                if job.state in {"suspected_stall", "idle"}:
                    job.state = "running"
                if checked["progress"] > 0:
                    job.progress_known = True
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
                job.progress_known = True
                reason = "progress"
            elif name == "failed":
                job.state = "failed"
                if checked["progress"] > 0:
                    job.progress_known = True
                reason = "failed"
            else:
                job.state = "completed"
                job.progress = 100
                job.progress_known = True
                reason = "completed"

            notify = self._stage(reason)
        if notify is not None and self._on_change is not None:
            self._on_change(notify)
        return self.view

    def tick(self, now: float) -> LightView:
        """Mark a missing heartbeat or expire a finished download hold."""
        notify: LightView | None = None
        with self._lock:
            changed_reason: str | None = None
            if (
                self._download is not None
                and self._download.hold_until is not None
                and now >= self._download.hold_until
            ):
                self._download = None
                changed_reason = "download_settled"

            if self._focus is not None:
                job = self._jobs[self._focus]
                if (
                    job.state in ALIVE
                    and job.last_heartbeat_at is not None
                    and now - job.last_heartbeat_at >= self.config.heartbeat_timeout_s
                ):
                    job.state = "suspected_stall"
                    changed_reason = "heartbeat_timeout"

            if changed_reason is not None:
                notify = self._stage(changed_reason)
        if notify is not None and self._on_change is not None:
            self._on_change(notify)
        return self.view

    def _build_job_view(self, reason: str) -> LightView:
        job_id = self._focus
        job = self._jobs[job_id] if job_id else None
        return LightView(
            state=job.state if job else "idle",
            job_id=job_id,
            progress=job.progress if job else 0,
            sequence=job.last_sequence if job else 0,
            reason=reason,
            progress_known=job.progress_known if job else False,
            display_mode=self._display_mode,
            charging_state=None,
        )

    def _build_battery_view(self, reason: str) -> LightView:
        if self._battery is None:
            return LightView(
                state="battery_unavailable",
                job_id=None,
                progress=0,
                sequence=0,
                reason=reason,
                progress_known=False,
                display_mode=self._display_mode,
                charging_state="unknown",
            )
        state = (
            "battery_charging"
            if self._battery.charging_state == "charging"
            else "battery"
        )
        return LightView(
            state=state,
            job_id=None,
            progress=self._battery.percent,
            sequence=0,
            reason=reason,
            progress_known=True,
            display_mode=self._display_mode,
            charging_state=self._battery.charging_state,
        )

    def _build_download_view(self, reason: str) -> LightView | None:
        if self._download is None:
            return None
        dl = self._download
        if dl.state == "failed":
            return LightView(
                state="failed",
                job_id=dl.download_id,
                progress=dl.progress,
                sequence=0,
                reason=reason,
                progress_known=dl.progress_known,
                display_mode=self._display_mode,
                charging_state=None,
            )
        if dl.state == "completed":
            return LightView(
                state="download",
                job_id=dl.download_id,
                progress=100,
                sequence=0,
                reason=reason,
                progress_known=True,
                display_mode=self._display_mode,
                charging_state=None,
            )
        return LightView(
            state="download",
            job_id=dl.download_id,
            progress=dl.progress,
            sequence=0,
            reason=reason,
            progress_known=dl.progress_known,
            display_mode=self._display_mode,
            charging_state=None,
        )

    def _compute_display_view(self, reason: str) -> LightView:
        job_view = self._build_job_view(reason)
        self._job_view = job_view

        if self._display_mode == "battery":
            return self._build_battery_view(reason)

        if self._display_mode == "job":
            return job_view

        # Default "auto" mode: active download (or its brief completion/failure hold) wins,
        # then active or failed jobs, then battery (when return_to_battery is enabled), else job_view.
        download_view = self._build_download_view(reason)
        if download_view is not None:
            return download_view

        if job_view.state in ACTIVE_OR_FAILED:
            return job_view

        if self._return_to_battery and self._battery is not None:
            if job_view.state in {"idle", "completed"}:
                return self._build_battery_view(reason)

        return job_view

    def _stage(self, reason: str) -> LightView | None:
        view = self._compute_display_view(reason)
        changed = (
            view.state != self._view.state
            or view.progress != self._view.progress
            or view.job_id != self._view.job_id
            or view.progress_known != self._view.progress_known
            or view.display_mode != self._view.display_mode
            or view.charging_state != self._view.charging_state
        )
        self._view = view
        return view if changed else None
