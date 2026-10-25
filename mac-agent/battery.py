"""Read macOS battery status and send deduplicated updates to Still Loading...

Uses ``pmset -g batt`` without root privileges or a shell. Never assumes the
MacBook is charging merely because AC power is attached; it inspects the
reported battery state token on the InternalBattery line.
"""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from messages import validate_battery_message
from simulator import format_timestamp

_BATT_LINE = re.compile(r"InternalBattery-\d+.*?(\d+)%\s*;\s*([^;\n]+)", re.IGNORECASE)

DEFAULT_POLL_INTERVAL_S = 15.0
DEFAULT_REFRESH_INTERVAL_S = 300.0
DEFAULT_MAX_BACKOFF_S = 60.0


@dataclass(frozen=True)
class BatteryReading:
    percent: int
    charging_state: str


def parse_pmset_batt(output: str) -> BatteryReading | None:
    """Parse ``pmset -g batt`` text into ``BatteryReading`` or ``None``.

    Reported states map to:
    - ``charging`` -> ``charging`` (or ``finishing charge`` below 100%)
    - ``discharging`` -> ``discharging``
    - ``charged`` -> ``full``
    - ``AC attached; not charging`` or any other token -> ``unknown``
    """
    if not isinstance(output, str) or not output.strip():
        return None

    for line in output.splitlines():
        match = _BATT_LINE.search(line)
        if not match:
            continue
        try:
            percent = int(match.group(1))
        except ValueError:
            return None
        if not 0 <= percent <= 100:
            return None

        raw_state = match.group(2).strip().lower()
        if raw_state == "charging":
            charging_state = "charging"
        elif raw_state == "finishing charge":
            charging_state = "full" if percent == 100 else "charging"
        elif raw_state == "discharging":
            charging_state = "discharging"
        elif raw_state == "charged":
            charging_state = "full"
        else:
            charging_state = "unknown"

        return BatteryReading(percent=percent, charging_state=charging_state)

    return None


def read_macos_battery(run_cmd=subprocess.run) -> BatteryReading | None:
    """Invoke ``pmset -g batt`` safely and return a ``BatteryReading`` or ``None``."""
    try:
        completed = run_cmd(
            ["pmset", "-g", "batt"],
            capture_output=True,
            text=True,
            timeout=3.0,
            check=False,
        )
    except (FileNotFoundError, PermissionError, subprocess.SubprocessError, OSError):
        return None

    if completed.returncode != 0 or not isinstance(completed.stdout, str):
        return None
    return parse_pmset_batt(completed.stdout)


def build_battery_message(
    reading: BatteryReading,
    *,
    now: datetime | None = None,
    display_mode: str | None = None,
    return_to_battery: bool | None = None,
) -> dict:
    moment = now or datetime.now(timezone.utc)
    payload: dict = {
        "schema_version": 1,
        "kind": "battery",
        "percent": reading.percent,
        "charging_state": reading.charging_state,
        "timestamp": format_timestamp(moment),
    }
    if display_mode is not None:
        payload["display_mode"] = display_mode
    if return_to_battery is not None:
        payload["return_to_battery"] = bool(return_to_battery)
    return validate_battery_message(payload)


def compute_backoff_delay(
    interval: float,
    consecutive_failures: int,
    *,
    max_backoff: float = DEFAULT_MAX_BACKOFF_S,
) -> float:
    """Return sleep duration in seconds after a poll.

    Normal polls sleep for ``interval``. Consecutive delivery failures back off
    exponentially (interval, 2*interval, 4*interval, ...) up to ``max_backoff``.
    """
    base = max(0.01, float(interval))
    if consecutive_failures <= 0:
        return base
    cap = max(base, float(max_backoff))
    delay = base * (2 ** (consecutive_failures - 1))
    return min(cap, delay)


class BatteryReporter:
    """Send battery updates when the reading/mode changes or refresh interval elapses."""

    def __init__(
        self,
        send_fn,
        *,
        read_fn=read_macos_battery,
        display_mode: str | None = None,
        return_to_battery: bool | None = None,
        refresh_interval_s: float | None = DEFAULT_REFRESH_INTERVAL_S,
        clock=time.monotonic,
    ) -> None:
        self._send_fn = send_fn
        self._read_fn = read_fn
        self.display_mode = display_mode
        self.return_to_battery = return_to_battery
        self.refresh_interval_s = refresh_interval_s
        self._clock = clock
        self._last_sent_key: tuple | None = None
        self._last_sent_at: float | None = None
        self._consecutive_failures: int = 0

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    def next_delay(
        self,
        interval: float = DEFAULT_POLL_INTERVAL_S,
        *,
        max_backoff: float = DEFAULT_MAX_BACKOFF_S,
    ) -> float:
        return compute_backoff_delay(
            interval,
            self._consecutive_failures,
            max_backoff=max_backoff,
        )

    def poll_once(self, *, force: bool = False) -> dict:
        now = float(self._clock())
        reading = self._read_fn()
        if reading is None:
            return {
                "status": "unavailable",
                "sent": False,
                "reading": None,
                "consecutive_failures": self._consecutive_failures,
            }
        key = (
            reading.percent,
            reading.charging_state,
            self.display_mode,
            self.return_to_battery,
        )
        refresh_due = (
            self._last_sent_at is not None
            and self.refresh_interval_s is not None
            and self.refresh_interval_s > 0
            and (now - self._last_sent_at) >= self.refresh_interval_s
        )
        if not force and not refresh_due and key == self._last_sent_key:
            return {
                "status": "unchanged",
                "sent": False,
                "reading": reading,
                "consecutive_failures": self._consecutive_failures,
            }

        message = build_battery_message(
            reading,
            display_mode=self.display_mode,
            return_to_battery=self.return_to_battery,
        )
        result = self._send_fn(message)
        delivered = bool(result.get("delivered"))
        if delivered:
            was_refresh = key == self._last_sent_key and not force
            self._last_sent_key = key
            self._last_sent_at = now
            self._consecutive_failures = 0
            return {
                "status": "sent",
                "refreshed": was_refresh,
                "sent": True,
                "reading": reading,
                "message": message,
                "delivery": result,
                "consecutive_failures": 0,
            }

        self._consecutive_failures += 1
        return {
            "status": "delivery_failed",
            "refreshed": False,
            "sent": False,
            "reading": reading,
            "message": message,
            "delivery": result,
            "consecutive_failures": self._consecutive_failures,
        }
