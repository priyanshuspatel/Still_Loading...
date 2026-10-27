"""Native macOS Desktop Notifications for Still Loading job events.

Sends Notification Center banner notifications on macOS using ``osascript``
so the developer is informed when long-running background tasks finish, fail,
or stall, even when working in another desktop space or window.

All notification dispatch is non-blocking; the calling thread is never
delayed by script execution.

Public API
----------
notify_completed(job_id, elapsed_seconds) -> None
notify_failed(job_id, elapsed_seconds, summary=None) -> None
notify_stall(job_id) -> None
notify(title, message, subtitle=None) -> None
is_available() -> bool
"""

from __future__ import annotations

import shutil
import subprocess
import threading
from typing import Optional


def is_available() -> bool:
    """Return True if ``osascript`` is on PATH and we are on macOS."""
    return shutil.which("osascript") is not None


def _escape_applescript(text: str) -> str:
    """Escape backslashes and double quotes for inclusion in an AppleScript string literal."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _format_duration(seconds: float) -> str:
    """Format duration in seconds into a friendly human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"


def notify(title: str, message: str, subtitle: Optional[str] = None) -> None:
    """Dispatch a native notification asynchronously.

    Parameters
    ----------
    title:
        The notification title (e.g. "Still Loading...").
    message:
        Main notification body text.
    subtitle:
        Optional subtitle line rendered below the title in macOS Notification Center.
    """
    if not is_available():
        return

    esc_title = _escape_applescript(title)
    esc_msg = _escape_applescript(message)
    if subtitle:
        esc_sub = _escape_applescript(subtitle)
        script = f'display notification "{esc_msg}" with title "{esc_title}" subtitle "{esc_sub}"'
    else:
        script = f'display notification "{esc_msg}" with title "{esc_title}"'

    def _worker() -> None:
        try:
            subprocess.Popen(
                ["osascript", "-e", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass

    thread = threading.Thread(target=_worker, daemon=True, name="still-loading-notification")
    thread.start()


def notify_completed(job_id: str, elapsed_seconds: float) -> None:
    """Send a notification when a job completes successfully."""
    dur = _format_duration(elapsed_seconds)
    notify(
        title="Still Loading...",
        subtitle="Job Completed",
        message=f"Job {job_id} finished in {dur}.",
    )


def notify_failed(job_id: str, elapsed_seconds: float, summary: Optional[str] = None) -> None:
    """Send a notification when a job fails, optionally including the failure summary."""
    dur = _format_duration(elapsed_seconds)
    if summary:
        body = f"Job {job_id} failed after {dur}: {summary}"
    else:
        body = f"Job {job_id} failed after {dur}."
    notify(
        title="Still Loading...",
        subtitle="Job Failed",
        message=body,
    )


def notify_stall(job_id: str) -> None:
    """Send a notification when a job is suspected of stalling."""
    notify(
        title="Still Loading...",
        subtitle="Suspected Stall",
        message=f"Job {job_id} heartbeats paused — check process liveness.",
    )
