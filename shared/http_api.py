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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from messages import JobLog, ProtocolError, parse_json_object, token_is_long_enough

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
        }
    view = engine.view
    return {
        "state": view.state,
        "code": view.code,
        "job_id": view.job_id,
        "progress": view.progress,
        "sequence": view.sequence,
    }


def _json_bytes(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


def make_handler(job_log: JobLog, token: str, announce: bool = False, engine=None):
    """Build a request handler closed over one job log and one token."""

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

        def do_POST(self) -> None:  # noqa: N802 - stdlib callback name
            if self.path.split("?", 1)[0] != "/v1/events":
                self._send(
                    404,
                    {
                        "status": "not_found",
                        "reason": "unknown_path",
                        "detail": "POST messages to /v1/events",
                    },
                )
                return
            if not self._authorized():
                return
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
                return
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
                return
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
                return
            raw = self.rfile.read(length)
            try:
                message = parse_json_object(raw)
                stored = job_log.accept(message)
            except ProtocolError as exc:
                self._send(
                    exc.status,
                    {"status": "rejected", "reason": exc.reason, "detail": exc.detail},
                )
                return
            if engine is not None:
                engine.apply(stored, time.monotonic())
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
) -> tuple[StillLoadingServer, JobLog]:
    if job_log is None:
        job_log = JobLog()
    handler = make_handler(job_log, token, announce=announce, engine=engine)
    httpd = StillLoadingServer((host, port), handler)
    return httpd, job_log
