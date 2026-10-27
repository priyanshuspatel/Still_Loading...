"""HTTP receiver used on the Mac during tests and on the UNO Q Linux side.

POST /v1/events stores one validated message.
GET /v1/jobs/<job_id> reads that job back. Both require the bearer token.
GET /health answers {"status": "ok"} and includes no job data.
GET /v1/lights returns the current light state and requires the same bearer token.
"""

from __future__ import annotations

import json
import secrets
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from history_store import HistoryStore, get_history_store
except ImportError:
    HistoryStore = None  # type: ignore
    get_history_store = lambda: None  # type: ignore

from messages import (
    JobLog,
    ProtocolError,
    parse_json_object,
    token_is_long_enough,
    validate_battery_message,
    validate_display_mode_message,
    validate_download_message,
)

HEALTH_BODY = {"status": "ok", "service": "still-loading"}


class StillLoadingServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def _lights_body(engine) -> dict:
    """Current lights. No token and no event log."""
    if engine is None:
        return {
            "state": "idle",
            "code": 0,
            "job_id": None,
            "progress": 0,
            "sequence": 0,
            "progress_known": False,
            "display_mode": "auto",
            "charging_state": None,
        }
    view = engine.view
    return {
        "state": view.state,
        "code": view.code,
        "job_id": view.job_id,
        "progress": view.progress,
        "sequence": view.sequence,
        "progress_known": view.progress_known,
        "display_mode": view.display_mode,
        "charging_state": view.charging_state,
    }


def _battery_body(engine) -> dict:
    if engine is None or engine.battery_view is None:
        return {
            "available": False,
            "percent": None,
            "charging_state": "unknown",
            "display_mode": "auto" if engine is None else engine.display_mode,
        }
    battery = engine.battery_view
    return {
        "available": True,
        "percent": battery.percent,
        "charging_state": battery.charging_state,
        "timestamp": battery.timestamp,
        "display_mode": engine.display_mode,
    }


def _download_body(engine) -> dict:
    if engine is None or engine.download_view is None:
        return {
            "active": False,
            "download_id": None,
            "state": "idle",
            "progress": 0,
            "progress_known": False,
            "downloaded_bytes": 0,
            "total_bytes": None,
            "display_mode": "auto" if engine is None else engine.display_mode,
        }
    dl = engine.download_view
    return {
        "active": dl.state in {"starting", "downloading", "completed", "failed"},
        "download_id": dl.download_id,
        "state": dl.state,
        "progress": dl.progress,
        "progress_known": dl.progress_known,
        "downloaded_bytes": dl.downloaded_bytes,
        "total_bytes": dl.total_bytes,
        "timestamp": dl.timestamp,
        "display_mode": engine.display_mode,
    }


def _json_bytes(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


def make_handler(
    job_log: JobLog,
    token: str,
    announce: bool = False,
    engine=None,
    history_store: HistoryStore | None = None,
):
    """Build a request handler closed over one job log, token, and optional history store."""
    if history_store is None and get_history_store is not None:
        try:
            history_store = get_history_store()
        except Exception:
            history_store = None

    class Handler(BaseHTTPRequestHandler):
        server_version = "StillLoading/1"
        # urllib on the Mac speaks HTTP/1.0 to this server without trouble.
        protocol_version = "HTTP/1.0"

        def log_message(self, fmt: str, *args) -> None:
            # The default logger writes every request to stderr. Accepted
            # events are printed on purpose from ``_announce``.
            return

        def _send(self, status: int, payload: dict) -> None:
            body = _json_bytes(payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            header = self.headers.get("Authorization", "")
            prefix = "Bearer "
            if not header.startswith(prefix):
                self._send(
                    401,
                    {
                        "status": "unauthorized",
                        "reason": "bad_token",
                        "detail": "Send Authorization: Bearer <token>",
                    },
                )
                return False
            presented = header[len(prefix) :]
            if not secrets.compare_digest(presented, token):
                self._send(
                    401,
                    {
                        "status": "unauthorized",
                        "reason": "bad_token",
                        "detail": "The token does not match this receiver",
                    },
                )
                return False
            return True

        def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
            path = self.path.split("?", 1)[0]
            if path == "/health":
                self._send(200, HEALTH_BODY)
                return
            if path == "/v1/lights":
                if not self._authorized():
                    return
                self._send(200, _lights_body(engine))
                return
            if path == "/v1/battery":
                if not self._authorized():
                    return
                self._send(200, _battery_body(engine))
                return
            if path == "/v1/download":
                if not self._authorized():
                    return
                self._send(200, _download_body(engine))
                return
            if path == "/v1/history":
                if not self._authorized():
                    return
                if history_store is None:
                    self._send(503, {"status": "error", "reason": "history_unavailable", "detail": "History store is not initialized"})
                    return
                query_str = self.path.split("?", 1)[1] if "?" in self.path else ""
                qparams = urllib.parse.parse_qs(query_str)
                limit = int(qparams.get("limit", [50])[0])
                offset = int(qparams.get("offset", [0])[0])
                failed_only = qparams.get("failed_only", ["0"])[0] in ("1", "true")
                jobs = history_store.list_jobs(limit=limit, offset=offset, failed_only=failed_only)
                self._send(200, {"status": "ok", "jobs": jobs, "count": len(jobs)})
                return
            if path == "/v1/history/stats":
                if not self._authorized():
                    return
                if history_store is None:
                    self._send(503, {"status": "error", "reason": "history_unavailable", "detail": "History store is not initialized"})
                    return
                stats = history_store.get_stats()
                self._send(200, {"status": "ok", "stats": stats})
                return
            prefix = "/v1/jobs/"
            if path.startswith(prefix):
                if not self._authorized():
                    return
                job_id = path[len(prefix) :]
                if not job_id or "/" in job_id:
                    self._send(
                        400,
                        {
                            "status": "rejected",
                            "reason": "invalid_field",
                            "detail": "The job id in the path is not usable",
                        },
                    )
                    return
                snapshot = job_log.snapshot(job_id)
                if snapshot is None:
                    self._send(
                        404,
                        {
                            "status": "not_found",
                            "reason": "unknown_job",
                            "detail": "This receiver has no accepted events for that job",
                        },
                    )
                    return
                self._send(200, snapshot)
                return
            self._send(
                404,
                {
                    "status": "not_found",
                    "reason": "unknown_path",
                    "detail": "Use GET /health, GET /v1/lights, or GET /v1/jobs/<job_id>",
                },
            )

        def _read_json_body(self) -> dict | None:
            content_type = self.headers.get("Content-Type", "")
            if "application/json" not in content_type:
                self._send(
                    400,
                    {
                        "status": "rejected",
                        "reason": "bad_content_type",
                        "detail": "Content-Type must be application/json",
                    },
                )
                return None
            length_header = self.headers.get("Content-Length")
            if length_header is None:
                self._send(
                    400,
                    {
                        "status": "rejected",
                        "reason": "missing_content_length",
                        "detail": "Content-Length is required",
                    },
                )
                return None
            try:
                length = int(length_header)
            except ValueError:
                length = -1
            if length < 0 or length > 8192:
                self._send(
                    400,
                    {
                        "status": "rejected",
                        "reason": "body_too_large",
                        "detail": "Message is larger than 8192 bytes",
                    },
                )
                return None
            raw = self.rfile.read(length)
            try:
                return parse_json_object(raw)
            except ProtocolError as exc:
                self._send(
                    exc.status,
                    {"status": "rejected", "reason": exc.reason, "detail": exc.detail},
                )
                return None

        def do_POST(self) -> None:  # noqa: N802 - stdlib callback name
            path = self.path.split("?", 1)[0]
            if path not in {
                "/v1/events",
                "/v1/battery",
                "/v1/display-mode",
                "/v1/download",
                "/v1/session/reset",
            }:
                self._send(
                    404,
                    {
                        "status": "not_found",
                        "reason": "unknown_path",
                        "detail": "POST messages to /v1/events, /v1/battery, /v1/download, /v1/display-mode, or /v1/session/reset",
                    },
                )
                return
            if not self._authorized():
                return
            message = self._read_json_body()
            if message is None:
                return

            if path == "/v1/download":
                try:
                    checked = validate_download_message(message)
                    if engine is not None:
                        engine.apply_download(checked, time.monotonic())
                except ProtocolError as exc:
                    self._send(
                        exc.status,
                        {"status": "rejected", "reason": exc.reason, "detail": exc.detail},
                    )
                    return
                if announce:
                    pct_label = (
                        f"{checked['progress']}%"
                        if checked["progress_known"]
                        else "indeterminate"
                    )
                    print(
                        f"accepted download {checked['state']} ({pct_label})",
                        flush=True,
                    )
                self._send(
                    202,
                    {
                        "status": "accepted",
                        "kind": "download",
                        "download_id": checked["download_id"],
                        "state": checked["state"],
                        "progress": checked["progress"],
                        "progress_known": checked["progress_known"],
                        "display_mode": "auto" if engine is None else engine.display_mode,
                    },
                )
                return

            if path == "/v1/battery":
                try:
                    checked = validate_battery_message(message)
                    if engine is not None:
                        engine.apply_battery(checked)
                except ProtocolError as exc:
                    self._send(
                        exc.status,
                        {"status": "rejected", "reason": exc.reason, "detail": exc.detail},
                    )
                    return
                if announce:
                    print(
                        f"accepted battery {checked['percent']}% ({checked['charging_state']})",
                        flush=True,
                    )
                self._send(
                    202,
                    {
                        "status": "accepted",
                        "kind": "battery",
                        "percent": checked["percent"],
                        "charging_state": checked["charging_state"],
                        "display_mode": "auto" if engine is None else engine.display_mode,
                    },
                )
                return

            if path == "/v1/session/reset":
                unknown = sorted(set(message) - {"target"})
                if unknown:
                    self._send(
                        400,
                        {
                            "status": "rejected",
                            "reason": "unknown_field",
                            "detail": "session reset accepts only target",
                        },
                    )
                    return
                target = message.get("target", "auto")
                try:
                    if engine is not None:
                        engine.session_command(target)
                    elif target not in {"idle", "auto"}:
                        raise ProtocolError(400, "invalid_field", "target must be idle or auto")
                except ProtocolError as exc:
                    self._send(
                        exc.status,
                        {"status": "rejected", "reason": exc.reason, "detail": exc.detail},
                    )
                    return
                if announce:
                    print(f"session reset target={target}", flush=True)
                self._send(
                    200,
                    {
                        "status": "ok",
                        "target": target,
                        "lights": _lights_body(engine),
                    },
                )
                return

            if path == "/v1/display-mode":
                try:
                    checked = validate_display_mode_message(message)
                    if engine is not None:
                        engine.set_display_mode(
                            checked["display_mode"],
                            return_to_battery=checked.get("return_to_battery"),
                        )
                except ProtocolError as exc:
                    self._send(
                        exc.status,
                        {"status": "rejected", "reason": exc.reason, "detail": exc.detail},
                    )
                    return
                if announce:
                    print(f"display_mode set to {checked['display_mode']}", flush=True)
                self._send(
                    200,
                    {
                        "status": "ok",
                        "display_mode": checked["display_mode"],
                        "lights": _lights_body(engine),
                    },
                )
                return

            try:
                stored = job_log.accept(message)
            except ProtocolError as exc:
                self._send(
                    exc.status,
                    {"status": "rejected", "reason": exc.reason, "detail": exc.detail},
                )
                return
            if engine is not None:
                engine.apply(stored, time.monotonic())
            if stored.get("event") in {"completed", "failed"} and history_store is not None:
                try:
                    snapshot = job_log.snapshot(stored["job_id"])
                    if snapshot:
                        history_store.record_job(job_log.events(stored["job_id"]), snapshot)
                except Exception:
                    pass
            if announce:
                print(
                    f"accepted job {stored['job_id']} "
                    f"sequence {stored['sequence']} {stored['event']}",
                    flush=True,
                )
            self._send(
                202,
                {
                    "status": "accepted",
                    "job_id": stored["job_id"],
                    "sequence": stored["sequence"],
                    "event": stored["event"],
                },
            )

    return Handler


def serve(
    host: str,
    port: int,
    token: str,
    announce: bool = False,
    engine=None,
    watch_interval: float = 0.5,
) -> tuple[StillLoadingServer, JobLog]:
    """Start a server in the current thread. Tests should use ``build_server``."""
    if not token_is_long_enough(token):
        raise ProtocolError(
            0,
            "short_token",
            "The token must be at least 16 characters. It is a shared secret, not a Wi-Fi password.",
        )
    httpd, job_log = build_server(host, port, token, announce=announce, engine=engine)
    print(f"Still Loading receiver listening on http://{host}:{port}", flush=True)
    if host == "0.0.0.0":
        print(
            "From the Mac, use the board's Wi-Fi IP or name.local address, not 0.0.0.0.",
            flush=True,
        )
    stop = threading.Event()
    if engine is not None:
        def watch() -> None:
            while not stop.wait(watch_interval):
                engine.tick(time.monotonic())

        threading.Thread(target=watch, name="still-loading-lights", daemon=True).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nReceiver stopped.", flush=True)
    finally:
        stop.set()
        httpd.server_close()
    return httpd, job_log


def build_server(
    host: str,
    port: int,
    token: str,
    job_log: JobLog | None = None,
    announce: bool = False,
    engine=None,
    history_store: HistoryStore | None = None,
) -> tuple[StillLoadingServer, JobLog]:
    if job_log is None:
        job_log = JobLog()
    handler = make_handler(job_log, token, announce=announce, engine=engine, history_store=history_store)
    httpd = StillLoadingServer((host, port), handler)
    return httpd, job_log
