"""App Lab polls GET /v1/lights. These tests stay on the Mac."""

from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "mac-agent"))
sys.path.insert(0, str(ROOT / "uno-q"))

from app_lab_main import (  # noqa: E402
    bridge_args,
    candidate_base_urls,
    forward_once,
    parse_default_gateway,
    resolve_token,
)
from http_api import build_server  # noqa: E402
from sender import post_event  # noqa: E402
from state_engine import StateEngine  # noqa: E402

TOKEN = "test-token-0123456789"


def started(job_id: str = "job-1") -> dict:
    return {
        "schema_version": 1,
        "event": "started",
        "job_id": job_id,
        "sequence": 1,
        "timestamp": "2026-01-01T00:00:00.000Z",
        "elapsed_seconds": 0,
        "progress": 0,
        "is_failure": False,
    }


class RouteTests(unittest.TestCase):
    def test_gateway_is_decoded_from_the_route_table(self) -> None:
        table = "Iface Destination Gateway Flags\neth0 00000000 0101A8C0 0003\n"
        self.assertEqual(parse_default_gateway(table), "192.168.1.1")
        urls = candidate_base_urls(env={}, route_text=table)
        self.assertEqual(urls[0], "http://192.168.1.1:8090")
        self.assertIn("http://127.0.0.1:8090", urls)

    def test_explicit_url_comes_first(self) -> None:
        urls = candidate_base_urls(
            env={"STILL_LOADING_LIGHTS_URL": "http://10.0.0.8:8090/"},
            route_text="",
        )
        self.assertEqual(urls[0], "http://10.0.0.8:8090")

    def test_token_comes_from_the_environment_or_a_file(self) -> None:
        self.assertEqual(
            resolve_token(
                env={"STILL_LOADING_TOKEN": "  abcdefghijklmnop "},
                token_file=Path("/missing"),
                search_defaults=False,
            ),
            "abcdefghijklmnop",
        )
        self.assertEqual(
            resolve_token(env={}, token_file=Path("/missing"), search_defaults=False),
            "",
        )


class ForwardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = StateEngine()
        self.httpd, _log = build_server("127.0.0.1", 0, TOKEN, engine=self.engine)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def test_lights_require_the_token_and_follow_an_accepted_event(self) -> None:
        request = urllib.request.Request(self.base + "/v1/lights", method="GET")
        with self.assertRaises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(request, timeout=2)
        self.assertEqual(denied.exception.code, 401)

        post_event(self.base, TOKEN, started("board-job"))
        calls: list[tuple[int, int]] = []
        status, pair = forward_once([self.base], TOKEN, lambda code, progress: calls.append((code, progress)), None)
        self.assertIn("forwarded running", status)
        self.assertEqual(calls, [(1, 0)])
        self.assertEqual(pair, (1, 0))
        again, pair = forward_once([self.base], TOKEN, lambda code, progress: calls.append((code, progress)), pair)
        self.assertTrue(again.startswith("unchanged"))
        self.assertEqual(calls, [(1, 0)])

    def test_health_still_has_no_job_data(self) -> None:
        with urllib.request.urlopen(self.base + "/health", timeout=2) as response:
            body = json.loads(response.read().decode("utf-8"))
        self.assertEqual(body, {"status": "ok", "service": "still-loading"})

    def test_bad_payload_is_not_forwarded(self) -> None:
        with self.assertRaises(ValueError):
            bridge_args({"code": 9, "progress": 0, "state": "running"})
        with self.assertRaises(ValueError):
            bridge_args({"code": True, "progress": 0, "state": "running"})


if __name__ == "__main__":
    unittest.main()
