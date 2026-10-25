"""App Lab companion. Paste this whole file into the Python tab.

The SSH receiver owns port 8090. This file does not listen on that port.
App Lab has its own filesystem, so it cannot see
/tmp/still-loading-lights.json. It asks the receiver over HTTP instead:

    GET /v1/lights
    Authorization: Bearer <the same token the Mac already uses>

Then it calls Bridge.call("set_job_lights", code, progress).

Leave TOKEN_OVERRIDE empty in git. If this App Lab process cannot see the
token any other way, type it into TOKEN_OVERRIDE in the App Lab editor only.
Do not copy that edited file back into the git repository.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

# Board-only override. Keep this empty in the repository.
TOKEN_OVERRIDE = ""
# Example if automatic discovery fails: "http://192.168.1.5:8090"
LIGHTS_URL_OVERRIDE = ""


def parse_default_gateway(route_text: str) -> str | None:
    """Read the default gateway from a /proc/net/route table.

    The gateway field is a little-endian hex IPv4 address. Destination
    00000000 is the default route.
    """
    for line in route_text.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 3:
            continue
        destination, gateway = parts[1], parts[2]
        if destination != "00000000" or gateway == "00000000":
            continue
        try:
            raw = bytes.fromhex(gateway)
        except ValueError:
            continue
        if len(raw) != 4:
            continue
        return ".".join(str(byte) for byte in raw[::-1])
    return None


def candidate_base_urls(env: dict | None = None, route_text: str = "") -> list[str]:
    """Places an App Lab container can reach the SSH receiver."""
    env = os.environ if env is None else env
    found: list[str] = []

    def add(url: str) -> None:
        cleaned = url.strip().rstrip("/")
        if cleaned and cleaned not in found:
            found.append(cleaned)

    add(env.get("STILL_LOADING_LIGHTS_URL", ""))
    add(LIGHTS_URL_OVERRIDE)
    gateway = parse_default_gateway(route_text)
    if gateway:
        add(f"http://{gateway}:8090")
    add("http://host.docker.internal:8090")
    add("http://127.0.0.1:8090")
    return found


def resolve_token(
    env: dict | None = None,
    token_file: Path | None = None,
    search_defaults: bool = True,
) -> str:
    """Find the existing bearer token. Never prints it."""
    env = os.environ if env is None else env
    for value in (TOKEN_OVERRIDE, env.get("STILL_LOADING_TOKEN", "")):
        if isinstance(value, str) and value.strip():
            return value.strip()
    paths = []
    if token_file is not None:
        paths.append(token_file)
    if search_defaults:
        paths.append(Path.home() / "still-loading-token")
        paths.append(Path("/home/arduino/still-loading-token"))
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text
    return ""


def bridge_args(payload: dict) -> tuple[int, int, str]:
    """Return (code, progress, state) for Bridge.call."""
    code = payload.get("code")
    progress = payload.get("progress")
    if isinstance(code, bool) or not isinstance(code, int) or not 0 <= code <= 9:
        raise ValueError("light code must be an integer from 0 to 9")
    if isinstance(progress, bool) or not isinstance(progress, int) or not 0 <= progress <= 100:
        raise ValueError("progress must be an integer from 0 to 100")
    state = payload.get("state", "")
    if not isinstance(state, str):
        raise ValueError("state must be a string")
    if state == "download" and payload.get("progress_known") is False:
        return 1, 0, state
    return code, progress, state


def fetch_lights(base_url: str, token: str, timeout: float = 1.0) -> dict:
    """GET /v1/lights. Raises urllib.error.URLError or HTTPError on failure."""
    request = urllib.request.Request(
        base_url.rstrip("/") + "/v1/lights",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("lights response must be a JSON object")
    return payload


def forward_once(
    base_urls: list[str],
    token: str,
    bridge_call,
    last_pair: tuple[int, int] | None,
    timeout: float = 1.0,
) -> tuple[str, tuple[int, int] | None]:
    """Poll the receiver and call bridge_call(code, progress) when the pair changes."""
    if not token:
        return "missing_token", last_pair
    last_error = "no candidate urls"
    for base_url in base_urls:
        try:
            payload = fetch_lights(base_url, token, timeout=timeout)
            code, progress, state = bridge_args(payload)
        except (urllib.error.URLError, ValueError, json.JSONDecodeError, OSError) as exc:
            last_error = f"{base_url}: {exc}"
            continue
        pair = (code, progress)
        if pair != last_pair:
            bridge_call(code, progress)
            return f"forwarded {state} code={code} progress={progress} via {base_url}", pair
        return f"unchanged {state} via {base_url}", last_pair
    return f"unreachable {last_error}", last_pair


def main() -> None:
    from arduino.app_utils import App, Bridge

    token = resolve_token()
    try:
        route_text = Path("/proc/net/route").read_text(encoding="utf-8")
    except OSError:
        route_text = ""
    urls = candidate_base_urls(route_text=route_text)
    if not token:
        print(
            "No token found. Export STILL_LOADING_TOKEN, create ~/still-loading-token, "
            "or set TOKEN_OVERRIDE in the App Lab editor. Do not commit the token.",
            flush=True,
        )
    else:
        print("Light forwarder will poll " + ", ".join(urls), flush=True)

    last_pair: tuple[int, int] | None = None
    told_unreachable = False

    def loop() -> None:
        nonlocal last_pair, told_unreachable
        status, last_pair = forward_once(
            urls,
            token,
            lambda code, progress: Bridge.call("set_job_lights", code, progress),
            last_pair,
        )
        if status.startswith("forwarded"):
            told_unreachable = False
            print(status, flush=True)
        elif status.startswith("unreachable") and not told_unreachable:
            told_unreachable = True
            print(status, flush=True)
        time.sleep(0.4 if token else 2)

    App.run(user_loop=loop)


if __name__ == "__main__":
    main()
