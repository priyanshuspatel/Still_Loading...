"""Run one local command and turn it into Still Loading events.

The command is a list of arguments. This module does not pass that list
through a shell. Stdout and stderr are stored separately. A process that
prints nothing is still healthy until it exits: silence is not a failure.

The wire events stay on schema version 1. The process id and the captured
text stay on the Mac. They are not fields the board accepts.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from messages import validate_message
from simulator import format_timestamp, new_job_id

MAX_CAPTURE_BYTES = 256 * 1024
_PERCENT = re.compile(r"(?<!\d)(100|[1-9]?\d)%")

try:
    from excerpt import safe_excerpt_for_event
except ImportError:
    # On the UNO Q the excerpt module may not be present.
    def safe_excerpt_for_event(stdout, stderr, **kwargs):
        return None

try:
    from explainer import explain_failure
except ImportError:
    def explain_failure(exit_code=1, message="", excerpt=None):
        return None


@dataclass
class ProcessRun:
    """Local record of one command. ``events`` are safe to send."""

    job_id: str
    pid: int | None
    started_at: str
    elapsed_seconds: float
    exit_code: int
    stdout: str
    stderr: str
    events: list[dict] = field(default_factory=list)
    stdout_truncated: bool = False
    stderr_truncated: bool = False


def _percent_in(line: str) -> int | None:
    found = _PERCENT.findall(line)
    if not found:
        return None
    return int(found[-1])


def _check_argv(argv: object) -> list[str]:
    if isinstance(argv, str) or not isinstance(argv, (list, tuple)):
        raise TypeError("Pass the command as a list of arguments, not a shell string")
    if not argv:
        raise ValueError("The command list is empty")
    checked: list[str] = []
    for item in argv:
        if not isinstance(item, str) or item == "":
            raise TypeError("Each argument must be a non-empty string")
        checked.append(item)
    return checked


class _Emitter:
    def __init__(self, job_id: str, started_at: datetime, origin: float, emit) -> None:
        self.job_id = job_id
        self.started_at = started_at
        self.origin = origin
        self.emit = emit
        self.events: list[dict] = []
        self.sequence = 0
        self.progress = 0
        self._lock = threading.Lock()

    def elapsed(self) -> float:
        return round(max(0.0, time.monotonic() - self.origin), 3)

    def send(self, event_name: str, **extra: object) -> dict:
        with self._lock:
            self.sequence += 1
            message: dict = {
                "schema_version": 1,
                "event": event_name,
                "job_id": self.job_id,
                "sequence": self.sequence,
                "timestamp": format_timestamp(datetime.now(timezone.utc)),
                "elapsed_seconds": self.elapsed(),
                "mode": "process",
                "source": "process",
                "progress": self.progress,
                "is_failure": False,
            }
            message.update(extra)
            if event_name == "progress":
                self.progress = int(message["progress"])
            checked = validate_message(message)
            self.events.append(checked)
            if self.emit is not None:
                self.emit(checked)
            return checked

    def note_progress(self, line: str) -> None:
        percent = _percent_in(line)
        if percent is None or percent == self.progress:
            return
        self.send("progress", progress=percent)


def _read_pipe(pipe, store: bytearray, truncated: list[bool], on_line) -> None:
    pending = bytearray()
    try:
        while True:
            chunk = pipe.read(4096)
            if not chunk:
                break
            room = MAX_CAPTURE_BYTES - len(store)
            if room > 0:
                store.extend(chunk[:room])
            if len(chunk) > room:
                truncated[0] = True
            pending.extend(chunk)
            while b"\n" in pending:
                line, _, pending = pending.partition(b"\n")
                on_line(line.decode("utf-8", errors="replace"))
        if pending:
            on_line(pending.decode("utf-8", errors="replace"))
    finally:
        pipe.close()


def _finish_failed(
    emitter: _Emitter,
    exit_code: int,
    message: str,
    stdout: str = "",
    stderr: str = "",
    include_excerpt: bool = True,
) -> None:
    extras: dict = {
        "progress": emitter.progress,
        "is_failure": True,
        "exit_code": exit_code,
        "message": message,
    }
    excerpt = None
    if include_excerpt:
        excerpt = safe_excerpt_for_event(stdout, stderr)
        if excerpt is not None:
            extras["excerpt"] = excerpt
    explanation = _explanation_for_failure(exit_code, message, excerpt)
    if explanation is not None:
        extras["explanation"] = explanation
    emitter.send("failed", **extras)


def _gemma_enabled() -> bool:
    return os.environ.get("GEMMA_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}


def _explanation_for_failure(exit_code: int, message: str, excerpt: str | None) -> dict | None:
    """Rules explanation, or a verified Gemma diagnosis when GEMMA_ENABLED is set.

    Gemma is skipped unless the operator opts in. A model failure becomes the
    rules explanation and does not stop the failed event.
    """
    if _gemma_enabled():
        try:
            from gemma_analysis import analyze_failure_logs

            return analyze_failure_logs(
                excerpt or "",
                exit_code=exit_code,
                message=message,
                failure_status="failed",
            ).to_explanation_dict()
        except Exception:
            logging.getLogger("still_loading.gemma").exception(
                "gemma analysis failed closed; using rules explainer"
            )
    exp = explain_failure(exit_code=exit_code, message=message, excerpt=excerpt)
    if exp is None:
        return None
    return exp.to_dict()


def run_process(
    argv: list[str] | tuple[str, ...],
    *,
    heartbeat_interval: float = 2.0,
    job_id: str | None = None,
    emit=None,
    include_excerpt: bool = True,
) -> ProcessRun:
    """Start ``argv`` and return its local record plus protocol events.

    ``emit`` is called with each validated event as it happens. Heartbeats
    continue while the process is alive, including when both pipes are empty.
    Exit code 0 becomes ``completed``. Any other exit becomes ``failed``.
    """
    command = _check_argv(argv)
    if heartbeat_interval <= 0:
        raise ValueError("heartbeat_interval must be greater than 0")

    job_id = job_id or new_job_id()
    started_at = datetime.now(timezone.utc)
    origin = time.monotonic()
    emitter = _Emitter(job_id, started_at, origin, emit)
    stdout_buf = bytearray()
    stderr_buf = bytearray()
    stdout_cut = [False]
    stderr_cut = [False]

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            shell=False,
        )
    except (FileNotFoundError, PermissionError, OSError):
        _finish_failed(emitter, 127, "Could not start the command")
        return ProcessRun(
            job_id=job_id,
            pid=None,
            started_at=format_timestamp(started_at),
            elapsed_seconds=emitter.elapsed(),
            exit_code=127,
            stdout="",
            stderr="",
            events=list(emitter.events),
        )

    assert process.stdout is not None
    assert process.stderr is not None
    stdout_thread = threading.Thread(
        target=_read_pipe,
        args=(process.stdout, stdout_buf, stdout_cut, emitter.note_progress),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_read_pipe,
        args=(process.stderr, stderr_buf, stderr_cut, emitter.note_progress),
        daemon=True,
    )
    emitter.send("started")
    stdout_thread.start()
    stderr_thread.start()

    next_heartbeat = heartbeat_interval
    try:
        while process.poll() is None:
            now = time.monotonic() - origin
            if now >= next_heartbeat:
                emitter.send("heartbeat")
                next_heartbeat += heartbeat_interval
            time.sleep(0.02)
    except KeyboardInterrupt:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
        stdout_thread.join()
        stderr_thread.join()
        stopped = process.returncode if process.returncode not in (None, 0) else 130
        _finish_failed(
            emitter,
            stopped,
            "Stopped by the user",
            stdout_buf.decode("utf-8", errors="replace"),
            stderr_buf.decode("utf-8", errors="replace"),
            include_excerpt=include_excerpt,
        )
        return _record(
            emitter,
            process.pid,
            started_at,
            stopped,
            stdout_buf,
            stderr_buf,
            stdout_cut[0],
            stderr_cut[0],
        )

    stdout_thread.join()
    stderr_thread.join()
    exit_code = process.returncode
    if exit_code is None:
        exit_code = 130
        _finish_failed(
            emitter,
            exit_code,
            "Process ended without an exit code",
            stdout_buf.decode("utf-8", errors="replace"),
            stderr_buf.decode("utf-8", errors="replace"),
            include_excerpt=include_excerpt,
        )
    elif exit_code == 0:
        emitter.progress = 100
        emitter.send("completed", progress=100, exit_code=0)
    else:
        _finish_failed(
            emitter,
            exit_code,
            f"Process exited with code {exit_code}",
            stdout_buf.decode("utf-8", errors="replace"),
            stderr_buf.decode("utf-8", errors="replace"),
            include_excerpt=include_excerpt,
        )

    return _record(
        emitter,
        process.pid,
        started_at,
        exit_code,
        stdout_buf,
        stderr_buf,
        stdout_cut[0],
        stderr_cut[0],
    )


def _record(
    emitter: _Emitter,
    pid: int | None,
    started_at: datetime,
    exit_code: int,
    stdout_buf: bytearray,
    stderr_buf: bytearray,
    stdout_truncated: bool,
    stderr_truncated: bool,
) -> ProcessRun:
    return ProcessRun(
        job_id=emitter.job_id,
        pid=pid,
        started_at=format_timestamp(started_at),
        elapsed_seconds=emitter.elapsed(),
        exit_code=exit_code,
        stdout=stdout_buf.decode("utf-8", errors="replace"),
        stderr=stderr_buf.decode("utf-8", errors="replace"),
        events=list(emitter.events),
        stdout_truncated=stdout_truncated,
        stderr_truncated=stderr_truncated,
    )
