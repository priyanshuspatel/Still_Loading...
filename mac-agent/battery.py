"""Read macOS battery status and send deduplicated updates to Still Loading...

Uses ``pmset -g batt`` without root privileges or a shell. Never assumes the
MacBook is charging merely because AC power is attached; it inspects the
reported battery state token on the InternalBattery line.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone

from messages import validate_battery_message
from simulator import format_timestamp

_BATT_LINE = re.compile(r"InternalBattery-\d+.*?(\d+)%\s*;\s*([^;\n]+)", re.IGNORECASE)


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


class BatteryReporter:
    """Send battery updates only when the reading or mode changes."""

    def __init__(
        self,
        send_fn,
        *,
        read_fn=read_macos_battery,
        display_mode: str | None = None,
        return_to_battery: bool | None = None,
    ) -> None:
        self._send_fn = send_fn
        self._read_fn = read_fn
        self.display_mode = display_mode
        self.return_to_battery = return_to_battery
        self._last_sent_key: tuple | None = None

    def poll_once(self, *, force: bool = False) -> dict:
        reading = self._read_fn()
        if reading is None:
            return {
                "status": "unavailable",
                "sent": False,
                "reading": None,
            }
        key = (
            reading.percent,
            reading.charging_state,
            self.display_mode,
            self.return_to_battery,
        )
        if not force and key == self._last_sent_key:
            return {
                "status": "unchanged",
                "sent": False,
                "reading": reading,
            }

        message = build_battery_message(
            reading,
            display_mode=self.display_mode,
            return_to_battery=self.return_to_battery,
        )
        result = self._send_fn(message)
        if result.get("delivered"):
            self._last_sent_key = key
        return {
            "status": "sent" if result.get("delivered") else "delivery_failed",
            "sent": bool(result.get("delivered")),
            "reading": reading,
            "message": message,
            "delivery": result,
        }
