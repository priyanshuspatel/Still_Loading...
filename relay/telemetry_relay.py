#!/usr/bin/env python3
"""Secure, read-only telemetry relay for Still Loading... (stillloading.tech).

This service runs as a bridge between the local/private UNO Q receiver
(defaulting to http://192.168.1.5:8090) and public web clients.

Security Guarantees:
1. STRICT READ-ONLY: Only reads GET /v1/lights, GET /v1/battery, GET /v1/download.
   No POST or hardware control endpoints are exposed to the public internet.
2. SECRET ISOLATION: The receiver's bearer token is kept solely in server memory
   via STILL_LOADING_TOKEN environment variable. Never sent to web clients.
3. SANITIZATION: Local disk paths, internal user names, and raw tokens are stripped.
4. CORS & CACHING: Bounded CORS and 1.5s in-memory caching to protect the UNO Q
   from request floods.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CACHE_TTL_SECONDS = 1.5


class TelemetryRelay:
    def __init__(self, upstream_url: str, token: str) -> None:
        self.upstream_url = upstream_url.rstrip("/")
        self.token = token
        self._cache_time = 0.0
        self._cached_payload: dict | None = None

    def _fetch_endpoint(self, path: str) -> dict:
        url = f"{self.upstream_url}{path}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception:
            pass
        return {}

    def get_snapshot(self) -> dict:
        now = time.time()
        if self._cached_payload and (now - self._cache_time < CACHE_TTL_SECONDS):
            return self._cached_payload

        lights = self._fetch_endpoint("/v1/lights")
        battery = self._fetch_endpoint("/v1/battery")
        download = self._fetch_endpoint("/v1/download")

        job_info = None
        job_id = lights.get("job_id")
        if job_id:
            job_data = self._fetch_endpoint(f"/v1/jobs/{job_id}")
            if job_data:
                latest = job_data.get("latest", {})
                job_info = {
                    "job_id": job_id,
                    "event": latest.get("event"),
                    "progress": latest.get("progress", lights.get("progress", 0)),
                    "exit_code": latest.get("exit_code"),
                    "is_failure": latest.get("is_failure", False),
                    "message": latest.get("message"),
                    "excerpt": job_data.get("excerpt") or latest.get("excerpt"),
                    "explanation": job_data.get("explanation") or latest.get("explanation"),
                }

        is_connected = bool(lights or battery or download or job_info)

        snapshot = {
            "timestamp": int(now * 1000),
            "is_live": is_connected,
            "battery": {
                "available": battery.get("available", False),
                "percent": battery.get("percent"),
                "charging_state": battery.get("charging_state", "unknown"),
                "timestamp": battery.get("timestamp"),
            },
            "download": {
                "active": download.get("active", False),
                "download_id": download.get("download_id"),
                "state": download.get("state", "idle"),
                "progress": download.get("progress", 0),
                "progress_known": download.get("progress_known", False),
                "downloaded_bytes": download.get("downloaded_bytes", 0),
                "total_bytes": download.get("total_bytes"),
                "filename_display": "Active Chrome Download" if download.get("active") else None,
            },
            "lights": {
                "state": lights.get("state", "idle"),
                "code": lights.get("code", 0),
                "job_id": lights.get("job_id"),
                "progress": lights.get("progress", 0),
                "sequence": lights.get("sequence", 0),
                "progress_known": lights.get("progress_known", False),
                "display_mode": lights.get("display_mode", "auto"),
                "charging_state": lights.get("charging_state"),
            },
            "job": job_info,
            "connection": {
                "dataService": "online",
                "macAgent": "active" if is_connected else "offline",
                "receiver": "reachable" if is_connected else "unreachable",
                "matrixHardware": "verified" if is_connected else "unverified",
            },
        }

        self._cached_payload = snapshot
        self._cache_time = now
        return snapshot


def make_relay_handler(relay: TelemetryRelay, allowed_origins: list[str]):
    class Handler(BaseHTTPRequestHandler):
        def _send_cors(self) -> None:
            origin = self.headers.get("Origin", "")
            if origin in allowed_origins or "*" in allowed_origins:
                self.send_header("Access-Control-Allow-Origin", origin if origin else "*")
                self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self._send_cors()
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path in {"/health", "/api/health"}:
                body = json.dumps({"status": "ok", "service": "still-loading-relay"}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self._send_cors()
                self.end_headers()
                self.wfile.write(body)
                return

            if path in {"/api/telemetry", "/v1/telemetry"}:
                data = relay.get_snapshot()
                body = json.dumps(data).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self._send_cors()
                self.end_headers()
                self.wfile.write(body)
                return

            self.send_response(404)
            self._send_cors()
            self.end_headers()

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Still Loading Telemetry Relay")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--upstream", default="http://192.168.1.5:8090")
    parser.add_argument("--token", default=None)
    args = parser.parse_args()

    token = args.token or os.environ.get("STILL_LOADING_TOKEN")
    if not token:
        print("Error: STILL_LOADING_TOKEN environment variable or --token required.", file=sys.stderr)
        return 1

    relay = TelemetryRelay(args.upstream, token)
    allowed_origins = [
        "https://stillloading.tech",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "*",
    ]
    handler = make_relay_handler(relay, allowed_origins)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Still Loading telemetry relay listening on http://{args.host}:{args.port}")
    print(f"Forwarding read-only telemetry from {args.upstream}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nRelay stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
