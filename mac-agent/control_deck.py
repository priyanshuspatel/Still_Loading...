#!/usr/bin/env python3
"""Local Control Deck for Still Loading...

The browser asks this process for an allowlisted action. This process calls
the existing Mac readers and the existing receiver. It does not accept a
shell command from the browser.

Gemma stays on the Mac. The UNO Q keeps its existing light codes.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "mac-agent"))

from battery import read_macos_battery  # noqa: E402
from explainer import explain_failure  # noqa: E402
from matrix_display import select_display_frame  # noqa: E402
from messages import ProtocolError, load_local_config, validate_message  # noqa: E402
from runner import run_process  # noqa: E402
from sender import (  # noqa: E402
    get_job,
    post_battery,
    post_display_mode,
    post_download,
    post_event,
    post_session_reset,
)
from simulator import format_timestamp, new_job_id  # noqa: E402

ACTIONS = frozenset(
    {
        "battery",
        "download",
        "job_success",
        "job_slow",
        "job_stall",
        "job_failure",
        "completed",
        "idle",
        "reset",
        "stop",
        "auto",
        "job_mode",
        "demo",
        "gemma",
        "connection",
    }
)
ASYNC_ACTIONS = frozenset(
    {"job_success", "job_slow", "job_stall", "job_failure", "completed", "demo"}
)
FORBIDDEN_FIELDS = frozenset({"command", "argv", "shell", "cmd"})

SUCCESS_ARGV = [sys.executable, "-c", "print('working 40%')\nprint('working 90%')"]
COMPLETED_ARGV = [sys.executable, "-c", "print('working 100%')"]
FAILURE_ARGV = [sys.executable, "-c", "import non_existent_pkg_xyz"]


def default_demo_plan() -> list[tuple]:
    """Scripted demonstration. Battery and download steps stay local."""
    return [
        ("preview", "battery", 82, "Battery 82%"),
        ("preview", "download", 0, "Download 0%"),
        ("preview", "download", 25, "Download 25%"),
        ("preview", "download", 50, "Download 50%"),
        ("preview", "download", 75, "Download 75%"),
        ("preview", "download", 100, "Download 100%"),
        ("action", "job_success"),
        ("action", "job_failure"),
        ("action", "job_stall"),
    ]


class ControlDeck:
    """One Mac-side owner for control actions, the event feed, and last lights."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        read_battery=read_macos_battery,
        make_download_reader=None,
        run_job=run_process,
        analyze=None,
        post_event_fn=post_event,
        post_battery_fn=post_battery,
        post_download_fn=post_download,
        post_display_mode_fn=post_display_mode,
        post_session_reset_fn=post_session_reset,
        get_job_fn=get_job,
        fetch_fn=None,
        sleep_fn=time.sleep,
        slow_gap_s: float = 6.2,
        heartbeat_every_s: float = 2.0,
        stall_wait_s: float = 7.0,
        demo_step_s: float = 0.6,
        demo_plan: list[tuple] | None = None,
        gemma_enabled: bool | None = None,
        config_path: str | None = None,
        spawn=None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._read_battery = read_battery
        self._make_download_reader = make_download_reader
        self._run_job = run_job
        self._analyze = analyze if analyze is not None else _analyze_with_gemma
        self._post_event = post_event_fn
        self._post_battery = post_battery_fn
        self._post_download = post_download_fn
        self._post_display_mode = post_display_mode_fn
        self._post_session_reset = post_session_reset_fn
        self._get_job = get_job_fn
        self._fetch = fetch_fn or self._fetch_upstream
        self._sleep = sleep_fn
        self.slow_gap_s = slow_gap_s
        self.heartbeat_every_s = heartbeat_every_s
        self.stall_wait_s = stall_wait_s
        self.demo_step_s = demo_step_s
        self.demo_plan = list(demo_plan) if demo_plan is not None else default_demo_plan()
        # None means decide at analysis time from the environment or a reachable
        # local Gemma endpoint. Tests pass True or False explicitly.
        self._gemma_flag = gemma_enabled
        self.config_path = config_path
        self._spawn = spawn or _spawn_monitor

        self._lock = threading.Lock()
        self._monitors: dict[str, object] = {}
        self._monitor_stop: set[str] = set()
        self._events: list[dict] = []
        self._next_id = 1
        self._cancel = threading.Event()
        self._op_thread: threading.Thread | None = None
        self._active_action: str | None = None
        self._download_stop = threading.Event()
        self._download_thread: threading.Thread | None = None
        self._last_lights: dict = {
            "state": "idle",
            "code": 0,
            "job_id": None,
            "progress": 0,
            "sequence": 0,
            "progress_known": False,
            "display_mode": "auto",
            "charging_state": None,
        }
        self._last_battery: dict = {
            "available": False,
            "percent": None,
            "charging_state": "unknown",
        }
        self._last_download: dict = {
            "active": False,
            "download_id": None,
            "state": "idle",
            "progress": 0,
            "progress_known": False,
            "downloaded_bytes": 0,
            "total_bytes": None,
        }
        self._last_job: dict | None = None
        self._uno = "offline"
        self._gemma: dict | None = None
        self._gemma_job_id: str | None = None
        self._demo_active = False
        self._demo_preview: dict | None = None
        self._announced_link: str | None = None
        self._log("SYSTEM", "Control Deck connected")

    def log_entries(self) -> list[dict]:
        with self._lock:
            return list(self._events)

    def wait_idle(self, timeout: float = 8.0) -> bool:
        thread = self._op_thread
        if thread is None:
            return True
        thread.join(timeout)
        return not thread.is_alive()

    def request(self, action: str, body: dict | None = None) -> tuple[int, dict]:
        payload = body or {}
        if not isinstance(payload, dict):
            return 400, {"status": "rejected", "reason": "not_an_object", "detail": "Body must be a JSON object"}
        forbidden = sorted(FORBIDDEN_FIELDS.intersection(payload))
        if forbidden:
            self._log("ERROR", "rejected a shell command field", level="error")
            return 400, {
                "status": "rejected",
                "reason": "forbidden_field",
                "detail": "The Control Deck does not accept shell commands",
            }
        if action not in ACTIONS:
            self._log("ERROR", f"rejected unknown action {action}", level="error")
            return 400, {
                "status": "rejected",
                "reason": "unknown_action",
                "detail": "Action is not in the Control Deck allowlist",
            }
        label = action.replace("_", " ")
        self._log("COMMAND", f"{label} requested")
        if action in ASYNC_ACTIONS:
            started = self._start_async(action, lambda: self._dispatch(action))
            if not started:
                self._log("ERROR", "another operation is still running", level="error")
                return 409, {
                    "status": "busy",
                    "reason": "busy",
                    "detail": "Wait for the current operation or press Stop",
                    "events": self.log_entries()[-40:],
                }
            return 202, {
                "status": "accepted",
                "action": action,
                "events": self.log_entries()[-40:],
                "state": self.snapshot(),
            }
        try:
            self._dispatch(action)
        except Exception as exc:  # noqa: BLE001 - the feed must show the failure
            self._log("ERROR", str(exc), level="error")
            return 500, {
                "status": "error",
                "detail": str(exc),
                "events": self.log_entries()[-40:],
                "state": self.snapshot(),
            }
        return 200, {
            "status": "ok",
            "action": action,
            "events": self.log_entries()[-40:],
            "state": self.snapshot(),
        }

    def snapshot(self) -> dict:
        self._pull_receiver()
        lights = dict(self._last_lights)
        preview = self._demo_preview
        simulated = preview is not None
        if simulated:
            lights = {
                **lights,
                "state": preview["state"],
                "progress": preview["progress"],
                "progress_known": True,
                "code": _code_for(preview["state"]),
            }
        frame_kind, frame = select_display_frame(
            lights.get("state") or "idle",
            int(lights.get("progress") or 0),
            0,
            progress_known=bool(lights.get("progress_known")),
        )
        job = self._last_job
        if job and self._gemma and job.get("job_id") == self._gemma_job_id:
            job = {**job, "explanation": self._gemma}
        return {
            "uno_q": self._uno,
            "lights": lights,
            "battery": self._last_battery,
            "download": self._last_download,
            "job": job,
            "gemma": self._gemma,
            "matrix": {
                "frame_kind": frame_kind,
                "frame": frame,
                "state": lights.get("state"),
                "progress": lights.get("progress", 0),
                "simulated": simulated,
            },
            "events": self.log_entries()[-80:],
            "demo": {
                "active": self._demo_active,
                "simulated": simulated,
                "label": "DEMO / SIMULATED" if simulated else None,
            },
            "display_mode": lights.get("display_mode", "auto"),
            "active_action": self._active_action,
            "timestamp": int(time.time() * 1000),
        }

    def telemetry_view(self) -> dict:
        """Relay-shaped snapshot so the existing developer dashboard keeps working."""
        snap = self.snapshot()
        connected = snap["uno_q"] == "connected"
        download = dict(snap["download"])
        download["filename_display"] = "Active Chrome Download" if download.get("active") else None
        return {
            "timestamp": snap["timestamp"],
            "is_live": connected,
            "battery": snap["battery"],
            "download": download,
            "lights": snap["lights"],
            "job": snap["job"],
            "connection": {
                "dataService": "online" if connected else "offline",
                "macAgent": "active",
                "receiver": "reachable" if connected else "unreachable",
                "matrixHardware": "verified" if connected else "unverified",
            },
        }

    def _dispatch(self, action: str) -> None:
        if action == "battery":
            self._do_battery()
        elif action == "download":
            self._do_download()
        elif action == "job_success":
            self._do_process_job("job_success", SUCCESS_ARGV)
        elif action == "completed":
            self._do_process_job("completed", COMPLETED_ARGV)
        elif action == "job_failure":
            self._do_failure()
        elif action == "job_slow":
            self._do_slow()
        elif action == "job_stall":
            self._do_stall()
        elif action == "idle":
            self._do_session("idle")
        elif action == "reset":
            self._do_reset()
        elif action == "stop":
            self._do_stop()
        elif action == "auto":
            self._do_mode("auto")
        elif action == "job_mode":
            self._do_mode("job")
        elif action == "demo":
            self._do_demo()
        elif action == "gemma":
            self._do_gemma()
        elif action == "connection":
            self._do_connection()

    def _start_async(self, action: str, fn) -> bool:
        with self._lock:
            if self._op_thread is not None and self._op_thread.is_alive():
                return False
            self._cancel = threading.Event()
            self._active_action = action

            def wrapped() -> None:
                try:
                    fn()
                except Exception as exc:  # noqa: BLE001
                    self._log("ERROR", f"{action} failed: {exc}", level="error")
                finally:
                    with self._lock:
                        self._active_action = None

            self._op_thread = threading.Thread(target=wrapped, name=f"control-{action}", daemon=True)
            self._op_thread.start()
            return True

    def monitor_argv(self, name: str) -> list[str]:
        """Fixed argv for an existing monitor. No shell and no caller-supplied command."""
        script = "battery_monitor.py" if name == "battery" else "download_monitor.py"
        config = self._monitor_config_path()
        # Run from mac-agent with the same relative config the terminal command uses.
        if config is not None and Path(config).resolve() == (ROOT / "mac-agent" / "config.local.json").resolve():
            argv = [sys.executable, script]
            if name == "battery":
                argv.extend(["--mode", "battery"])
            else:
                argv.extend(["--interval", "0.25"])
            argv.extend(["--config", "config.local.json"])
            return argv
        argv = [sys.executable, str(ROOT / "mac-agent" / script)]
        if name == "battery":
            argv.extend(["--mode", "battery"])
        else:
            argv.extend(["--interval", "0.25"])
        if config is not None:
            argv.extend(["--config", config])
            return argv
        argv.extend(["--url", self.base_url, "--token", self.token])
        return argv

    def _monitor_config_path(self) -> str | None:
        if not self.config_path:
            return None
        path = Path(self.config_path)
        if not path.is_file():
            return None
        return str(path)

    def _monitor_running(self, name: str) -> bool:
        proc = self._monitors.get(name)
        return proc is not None and proc.poll() is None

    def _start_monitor(self, name: str) -> bool:
        """Start one existing monitor process, or keep the one already running."""
        with self._lock:
            if self._monitor_running(name):
                already = True
                proc = None
            else:
                already = False
                argv = self.monitor_argv(name)
                self._monitor_stop.discard(name)
                try:
                    proc = self._spawn(argv)
                except OSError as exc:
                    proc = exc
                else:
                    self._monitors[name] = proc
        if already:
            self._log(name.upper(), "monitor already running")
            return False
        if isinstance(proc, OSError):
            self._log("ERROR", f"{name} monitor failed to start: {proc}", level="error")
            return False
        self._log(name.upper(), "monitor started")
        threading.Thread(
            target=self._watch_monitor,
            args=(name, proc),
            name=f"watch-{name}",
            daemon=True,
        ).start()
        stdout = getattr(proc, "stdout", None)
        if stdout is not None:
            threading.Thread(
                target=self._relay_monitor_output,
                args=(name, stdout),
                name=f"log-{name}",
                daemon=True,
            ).start()
        return True

    def _relay_monitor_output(self, name: str, stream) -> None:
        try:
            for line in stream:
                text = line.strip()
                if text:
                    self._log(name.upper(), text)
        except Exception as exc:  # noqa: BLE001
            self._log("ERROR", f"{name} monitor output stopped: {exc}", level="error")

    def _watch_monitor(self, name: str, proc) -> None:
        try:
            code = proc.wait()
        except Exception as exc:  # noqa: BLE001
            self._log("ERROR", f"{name} monitor wait failed: {exc}", level="error")
            code = None
        with self._lock:
            current = self._monitors.get(name)
            if current is proc:
                self._monitors.pop(name, None)
            requested = name in self._monitor_stop
            self._monitor_stop.discard(name)
        if not requested:
            self._log("ERROR", f"{name} monitor exited ({code})", level="error")

    def _stop_monitor(self, name: str) -> None:
        with self._lock:
            proc = self._monitors.get(name)
            if proc is None or proc.poll() is not None:
                return
            self._monitor_stop.add(name)
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        except Exception as exc:  # noqa: BLE001
            self._log("ERROR", f"{name} monitor stop failed: {exc}", level="error")
        self._log(name.upper(), "monitor stopped")

    def _stop_monitors(self) -> None:
        self._stop_monitor("battery")
        self._stop_monitor("download")

    def _do_battery(self) -> None:
        # The battery command forces battery display mode. Stop the download
        # monitor so the two commands do not fight over the matrix.
        self._stop_monitor("download")
        started = self._start_monitor("battery")
        if started:
            self._log("BATTERY", "battery monitor running")
        self._pull_receiver()

    def _do_download(self) -> None:
        # battery_monitor.py --mode battery reasserts battery display on every
        # reading and would hide the download percentage on the Arduino.
        self._stop_monitor("battery")
        self._log("DOWNLOAD", "Checking Chrome downloads")
        mode = self._post_display_mode(self.base_url, self.token, "auto")
        self._note_delivery(mode, "auto priority")
        started = self._start_monitor("download")
        if started:
            self._log("DOWNLOAD", "download monitor running")
        self._pull_receiver()

    def _do_process_job(self, name: str, argv: list[str]) -> None:
        self._log("JOB", f"starting {name}")
        self._do_mode("job")
        result = self._run_job(argv, emit=self._forward_job_event, cancel=self._cancel)
        self._remember_job(result)
        self._announce_lights()

    def _do_failure(self) -> None:
        self._log("JOB", "starting failing demo job")
        self._do_mode("job")
        saved = os.environ.get("GEMMA_ENABLED")
        os.environ["GEMMA_ENABLED"] = "0"
        try:
            result = self._run_job(
                FAILURE_ARGV,
                emit=self._forward_job_event,
                cancel=self._cancel,
            )
        finally:
            if saved is None:
                os.environ.pop("GEMMA_ENABLED", None)
            else:
                os.environ["GEMMA_ENABLED"] = saved
        self._remember_job(result)
        self._announce_lights()
        failed = next((event for event in reversed(result.events) if event.get("event") == "failed"), None)
        excerpt = ""
        message = "Process exited with code 1"
        exit_code = result.exit_code if result.exit_code is not None else 1
        if failed:
            excerpt = str(failed.get("excerpt") or "")
            message = str(failed.get("message") or message)
            exit_code = int(failed.get("exit_code") or exit_code)
        self._explain(excerpt, exit_code, message, result.job_id)

    def _do_slow(self) -> None:
        self._log("JOB", "starting slow job")
        self._do_mode("job")
        job_id = new_job_id()
        origin = time.monotonic()
        self._send_scripted(job_id, 1, "started", 0, False, origin)
        self._send_scripted(job_id, 2, "progress", 20, False, origin)
        elapsed = 0.0
        sequence = 2
        while elapsed < self.slow_gap_s:
            if self._cancel.is_set():
                self._log("JOB", "slow job stopped")
                return
            step = min(self.heartbeat_every_s, self.slow_gap_s - elapsed)
            self._sleep(step)
            elapsed += step
            sequence += 1
            self._send_scripted(job_id, sequence, "heartbeat", 20, False, origin)
        sequence += 1
        self._send_scripted(job_id, sequence, "progress", 55, False, origin)
        self._log("JOB", "slow")
        self._announce_lights()

    def _do_stall(self) -> None:
        self._log("JOB", "starting stall watch")
        self._do_mode("job")
        job_id = new_job_id()
        origin = time.monotonic()
        self._send_scripted(job_id, 1, "started", 0, False, origin)
        self._send_scripted(job_id, 2, "progress", 30, False, origin)
        self._send_scripted(job_id, 3, "heartbeat", 30, False, origin)
        self._log("WATCHDOG", "heartbeats stopped")
        waited = 0.0
        while waited < self.stall_wait_s:
            if self._cancel.is_set():
                self._log("WATCHDOG", "stall watch stopped")
                return
            step = min(0.2, self.stall_wait_s - waited)
            self._sleep(step)
            waited += step
            self._pull_receiver()
            if self._last_lights.get("state") == "suspected_stall":
                self._log("WATCHDOG", "suspected stall")
                self._log(
                    "UNO Q",
                    f"state={self._last_lights.get('code')} progress={self._last_lights.get('progress')}",
                )
                return
        self._pull_receiver()
        state = self._last_lights.get("state")
        if state == "suspected_stall":
            self._log("WATCHDOG", "suspected stall")
        else:
            self._log("WATCHDOG", f"waiting finished in state {state}")
        self._announce_lights()

    def _explain(self, excerpt: str, exit_code: int, message: str, job_id: str | None) -> None:
        self._log("GEMMA", "analyzing redacted logs")
        if self._gemma_flag is False:
            explanation = _rules_card(exit_code, message, excerpt)
        else:
            try:
                explanation = self._analyze(excerpt, exit_code=exit_code, message=message)
            except Exception as exc:  # noqa: BLE001
                explanation = _rules_card(exit_code, message, excerpt, detail=str(exc))
                self._log("ERROR", f"Gemma failed closed: {exc}", level="error")
        status = str(explanation.get("verification_status") or "unavailable")
        self._gemma = explanation
        self._gemma_job_id = job_id
        if status == "verified":
            self._log("GEMMA", "evidence verified")
        elif status == "unavailable":
            self._log("GEMMA", "Gemma unavailable — rules explanation used")
        else:
            self._log("GEMMA", f"evidence {status}")
        self._pull_receiver()

    def _do_gemma(self) -> None:
        self._pull_receiver()
        job = self._last_job or {}
        excerpt = str(job.get("excerpt") or "")
        if not job.get("is_failure") or not excerpt:
            self._log("GEMMA", "no failed job to analyze")
            return
        exit_code = int(job.get("exit_code") or 1)
        message = str(job.get("message") or "Process exited with code 1")
        self._explain(excerpt, exit_code, message, job.get("job_id"))

    def _do_connection(self) -> None:
        self._pull_receiver()
        lights = self._last_lights
        if self._uno == "connected":
            self._log(
                "UNO Q",
                f"CONNECTED state={lights.get('code')} {lights.get('state')}",
            )
        else:
            self._log("UNO Q", "OFFLINE", level="error")

    def _do_session(self, target: str) -> None:
        self._log("SYSTEM", f"session {target}")
        result = self._post_session_reset(self.base_url, self.token, target)
        self._note_delivery(result, f"session {target}")
        self._announce_lights()

    def _do_reset(self) -> None:
        self._log("SYSTEM", "reset")
        self._cancel.set()
        self._stop_monitors()
        self._download_stop.set()
        self._demo_active = False
        self._demo_preview = None
        self._gemma = None
        self._gemma_job_id = None
        self._do_session("auto")
        self._log("SYSTEM", "automatic idle")

    def _do_stop(self) -> None:
        self._cancel.set()
        self._stop_monitors()
        self._download_stop.set()
        self._log("SYSTEM", "stop requested")
        self._pull_receiver()

    def _do_mode(self, mode: str) -> None:
        self._log("SYSTEM", f"display mode {mode}")
        result = self._post_display_mode(self.base_url, self.token, mode)
        self._note_delivery(result, f"display mode {mode}")
        self._announce_lights()

    def _do_demo(self) -> None:
        self._demo_active = True
        self._log("DEMO", "DEMO / SIMULATED sequence started", simulated=True)
        try:
            for step in self.demo_plan:
                if self._cancel.is_set():
                    self._log("DEMO", "stopped", simulated=True)
                    return
                kind = step[0]
                if kind == "preview":
                    _, state, progress, text = step
                    self._demo_preview = {
                        "state": state,
                        "progress": int(progress),
                        "simulated": True,
                    }
                    self._log("DEMO", f"{text} DEMO / SIMULATED", simulated=True)
                    self._sleep(self.demo_step_s)
                elif kind == "action":
                    self._demo_preview = None
                    self._dispatch(step[1])
                else:
                    self._log("ERROR", "unknown demo step", level="error")
        finally:
            self._demo_active = False
            self._demo_preview = None
            self._log("DEMO", "sequence finished", simulated=True)

    def _send_scripted(
        self,
        job_id: str,
        sequence: int,
        event: str,
        progress: int,
        is_failure: bool,
        origin: float,
    ) -> None:
        message = {
            "schema_version": 1,
            "event": event,
            "job_id": job_id,
            "sequence": sequence,
            "timestamp": format_timestamp(datetime.now(timezone.utc)),
            "elapsed_seconds": round(max(0.0, time.monotonic() - origin), 3),
            "progress": progress,
            "is_failure": is_failure,
            "mode": "control",
            "source": "control",
        }
        if event == "completed":
            message["exit_code"] = 0
            message["progress"] = 100
        checked = validate_message(message)
        result = self._post_event(self.base_url, self.token, checked)
        self._log("JOB", f"{event} progress={checked['progress']}")
        self._note_delivery(result, event)
        self._last_job = {
            "job_id": job_id,
            "event": event,
            "progress": checked["progress"],
            "is_failure": is_failure,
            "explanation": None,
        }

    def _forward_job_event(self, event: dict) -> None:
        result = self._post_event(self.base_url, self.token, event)
        self._log("JOB", f"{event['event']} progress={event.get('progress')}")
        self._note_delivery(result, str(event.get("event")))

    def _remember_job(self, result) -> None:
        latest = result.events[-1] if result.events else {}
        self._last_job = {
            "job_id": result.job_id,
            "event": latest.get("event"),
            "progress": latest.get("progress", 0),
            "exit_code": result.exit_code,
            "is_failure": bool(latest.get("is_failure")),
            "message": latest.get("message"),
            "excerpt": latest.get("excerpt"),
            "explanation": latest.get("explanation"),
        }

    def _note_delivery(self, result: dict, label: str) -> None:
        if result.get("delivered"):
            self._pull_receiver()
            lights = self._last_lights
            self._log(
                "UNO Q",
                f"state={lights.get('code')} progress={lights.get('progress')} {label}",
            )
            return
        detail = ""
        body = result.get("body")
        if isinstance(body, dict):
            detail = str(body.get("detail") or body.get("reason") or "")
        detail = detail or str(result.get("detail") or result.get("reason") or "unreachable")
        self._log("ERROR", f"UNO Q receiver unreachable ({detail})", level="error")
        self._publish_link("offline")

    def _announce_lights(self) -> None:
        self._pull_receiver()
        lights = self._last_lights
        kind, _frame = select_display_frame(
            str(lights.get("state") or "idle"),
            int(lights.get("progress") or 0),
            0,
            progress_known=bool(lights.get("progress_known")),
        )
        self._log("MATRIX", f"{kind} state={lights.get('state')} progress={lights.get('progress')}")
        self._log("UNO Q", f"state={lights.get('code')} progress={lights.get('progress')}")

    def _publish_link(self, status: str) -> None:
        self._uno = status
        if self._announced_link == status:
            return
        self._announced_link = status
        if status == "connected":
            self._log("UNO Q", "CONNECTED")
        else:
            self._log("UNO Q", "OFFLINE", level="error")

    def _pull_receiver(self) -> None:
        lights = self._fetch("/v1/lights")
        battery = self._fetch("/v1/battery")
        download = self._fetch("/v1/download")
        if lights is None and battery is None and download is None:
            self._publish_link("offline")
            return
        self._publish_link("connected")
        if isinstance(lights, dict) and lights:
            self._last_lights = {
                "state": lights.get("state", "idle"),
                "code": lights.get("code", 0),
                "job_id": lights.get("job_id"),
                "progress": lights.get("progress", 0),
                "sequence": lights.get("sequence", 0),
                "progress_known": bool(lights.get("progress_known")),
                "display_mode": lights.get("display_mode", "auto"),
                "charging_state": lights.get("charging_state"),
            }
        if isinstance(battery, dict) and battery:
            self._last_battery = {
                "available": bool(battery.get("available")),
                "percent": battery.get("percent"),
                "charging_state": battery.get("charging_state", "unknown"),
                "timestamp": battery.get("timestamp"),
                "simulated": False,
            }
        if isinstance(download, dict) and download:
            self._last_download = {
                "active": bool(download.get("active")),
                "download_id": download.get("download_id"),
                "state": download.get("state", "idle"),
                "progress": download.get("progress", 0),
                "progress_known": bool(download.get("progress_known")),
                "downloaded_bytes": download.get("downloaded_bytes", 0),
                "total_bytes": download.get("total_bytes"),
                "simulated": False,
            }
        job_id = self._last_lights.get("job_id")
        if job_id:
            job = self._fetch(f"/v1/jobs/{job_id}")
            if isinstance(job, dict) and job.get("job_id"):
                latest = job.get("latest") or {}
                self._last_job = {
                    "job_id": job_id,
                    "event": latest.get("event"),
                    "progress": latest.get("progress", self._last_lights.get("progress", 0)),
                    "exit_code": latest.get("exit_code"),
                    "is_failure": bool(latest.get("is_failure")),
                    "message": latest.get("message"),
                    "excerpt": job.get("excerpt") or latest.get("excerpt"),
                    "explanation": job.get("explanation") or latest.get("explanation"),
                }

    def _fetch_upstream(self, path: str) -> dict | None:
        request = urllib.request.Request(
            self.base_url + path,
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=2.0) as response:
                if response.status != 200:
                    return None
                payload = json.loads(response.read().decode("utf-8"))
                return payload if isinstance(payload, dict) else None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            return None

    def _log(self, source: str, action: str, *, level: str = "info", simulated: bool = False) -> None:
        moment = datetime.now().astimezone()
        entry = {
            "id": 0,
            "timestamp": moment.strftime("%H:%M:%S"),
            "epoch_ms": int(moment.timestamp() * 1000),
            "source": source,
            "action": action,
            "level": level,
            "simulated": simulated,
        }
        with self._lock:
            entry["id"] = self._next_id
            self._next_id += 1
            self._events.append(entry)
            if len(self._events) > 200:
                del self._events[: len(self._events) - 200]


def _code_for(state: str) -> int:
    codes = {
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
    return codes.get(state, 0)


def _rules_card(exit_code: int, message: str, excerpt: str, detail: str = "") -> dict:
    explained = explain_failure(exit_code=exit_code, message=message, excerpt=excerpt or None)
    if explained is None:
        summary = message or "Failure recorded"
        suggestion = "Inspect the redacted log excerpt."
        category = "generic_error"
        confidence = 0.4
    else:
        summary = explained.summary
        suggestion = explained.suggestion
        category = explained.category
        confidence = explained.confidence
    return {
        "category": category,
        "summary": summary,
        "suggestion": suggestion,
        "confidence": confidence,
        "source": "rules",
        "severity": "error",
        "verification_status": "unavailable",
        "diagnosis": summary,
        "recommended_action": suggestion,
        "evidence": [],
        "fallback_summary": summary,
        "detail": detail or "Gemma unavailable — rules explanation used",
    }


def _analyze_with_gemma(excerpt: str, *, exit_code: int, message: str) -> dict:
    from gemma_analysis import analyze_failure_logs
    from gemma_client import resolve_control_gemma_config

    return analyze_failure_logs(
        excerpt or "",
        exit_code=exit_code,
        message=message,
        failure_status="failed",
        config=resolve_control_gemma_config(),
    ).to_explanation_dict()


def _spawn_monitor(argv: list[str]):
    """Start one existing monitor script. The argument list is fixed by the deck."""
    return subprocess.Popen(
        argv,
        cwd=str(ROOT / "mac-agent"),
        start_new_session=True,
    )


def _json_bytes(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


def make_control_handler(deck: ControlDeck):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def log_message(self, fmt: str, *args) -> None:
            return

        def _cors(self) -> None:
            origin = self.headers.get("Origin", "")
            allow = origin or "*"
            self.send_header("Access-Control-Allow-Origin", allow)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

        def _send(self, status: int, payload: dict) -> None:
            body = _json_bytes(payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self._cors()
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path in {"/health", "/api/health"}:
                self._send(200, {"status": "ok", "service": "still-loading-control"})
                return
            if path == "/v1/control/state":
                self._send(200, deck.snapshot())
                return
            if path in {"/api/telemetry", "/v1/telemetry"}:
                self._send(200, deck.telemetry_view())
                return
            if path == "/v1/events":
                self._send(200, {"events": deck.log_entries()})
                return
            if path == "/v1/gemma/latest":
                self._send(200, {"gemma": deck.snapshot().get("gemma")})
                return
            if path == "/v1/matrix":
                snap = deck.snapshot()
                self._send(200, snap["matrix"])
                return
            self._send(404, {"status": "not_found", "reason": "unknown_path"})

        def do_POST(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            raw = self._read_body()
            if raw is None:
                return
            routes = {
                "/v1/control/battery": "battery",
                "/v1/control/download": "download",
                "/v1/control/idle": "idle",
                "/v1/control/reset": "reset",
                "/v1/control/stop": "stop",
                "/v1/control/gemma": "gemma",
                "/v1/control/connection": "connection",
            }
            if path in routes:
                status, payload = deck.request(routes[path], raw)
                self._send(status, payload)
                return
            if path == "/v1/control/job":
                action = raw.get("action")
                if action not in {"job_success", "job_slow", "job_stall", "job_failure", "completed"}:
                    status, payload = deck.request(str(action or ""), raw)
                    self._send(status if status == 400 else 400, payload if status == 400 else {
                        "status": "rejected",
                        "reason": "unknown_action",
                        "detail": "job action must be an allowlisted demo job",
                    })
                    return
                status, payload = deck.request(action, raw)
                self._send(status, payload)
                return
            if path == "/v1/control/demo":
                action = raw.get("action", "demo")
                status, payload = deck.request(str(action), raw)
                self._send(status, payload)
                return
            if path == "/v1/control/mode":
                mode = raw.get("mode")
                mapped = {"auto": "auto", "job": "job_mode", "battery": "battery"}.get(mode)
                if mapped is None:
                    self._send(400, {
                        "status": "rejected",
                        "reason": "unknown_action",
                        "detail": "mode must be auto, job, or battery",
                    })
                    return
                status, payload = deck.request(mapped, raw)
                self._send(status, payload)
                return
            self._send(404, {"status": "not_found", "reason": "unknown_path"})

        def _read_body(self) -> dict | None:
            length_header = self.headers.get("Content-Length")
            if length_header is None:
                return {}
            try:
                length = int(length_header)
            except ValueError:
                length = -1
            if length < 0 or length > 4096:
                self._send(400, {"status": "rejected", "reason": "body_too_large", "detail": "Body is too large"})
                return None
            if length == 0:
                return {}
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send(400, {"status": "rejected", "reason": "malformed_json", "detail": "Body is not JSON"})
                return None
            if not isinstance(payload, dict):
                self._send(400, {"status": "rejected", "reason": "not_an_object", "detail": "Body must be a JSON object"})
                return None
            return payload

    return Handler


def build_control_server(deck: ControlDeck, host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_control_handler(deck))


def _load_target(config_path: str | None, url: str | None, token: str | None) -> tuple[str, str]:
    host = "127.0.0.1"
    port = 8090
    # The config file token belongs to the board. An explicit --token overrides it.
    # The environment is only a fallback so a loopback test token cannot replace
    # the token stored for the physical receiver.
    loaded_token = token or ""
    if config_path:
        data = load_local_config(Path(config_path))
        host = str(data.get("host") or host)
        port = int(data.get("port") or port)
        if not loaded_token:
            loaded_token = str(data.get("token") or "")
    if not loaded_token:
        loaded_token = os.environ.get("STILL_LOADING_TOKEN") or ""
    if url:
        base = url.rstrip("/")
    else:
        base = f"http://{host}:{port}"
    if len(loaded_token.strip()) < 16:
        raise ProtocolError(
            0,
            "short_token",
            "Set STILL_LOADING_TOKEN or pass --config with a token of at least 16 characters.",
        )
    return base, loaded_token.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Still Loading Control Deck")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--upstream", default=None, help="Receiver base URL. Defaults to the config host.")
    parser.add_argument("--token", default=None)
    parser.add_argument("--config", default=None)
    args = parser.parse_args(argv)
    try:
        base_url, token = _load_target(args.config, args.upstream, args.token)
    except ProtocolError as exc:
        print(exc.detail, file=sys.stderr)
        return 2
    config_path = args.config
    if config_path is None:
        default_config = ROOT / "mac-agent" / "config.local.json"
        if default_config.is_file():
            config_path = str(default_config)
    # A config file names the physical board. An explicit --upstream is only
    # for a loopback receiver; otherwise the deck must read the same board
    # the monitors update.
    if args.upstream is None and config_path:
        base_url, token = _load_target(config_path, None, args.token)
    deck = ControlDeck(base_url, token, config_path=config_path)
    server = build_control_server(deck, args.host, args.port)
    print(f"Still Loading Control Deck on http://{args.host}:{args.port}")
    print(f"Receiver {base_url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nControl Deck stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
