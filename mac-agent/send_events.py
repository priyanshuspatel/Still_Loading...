"""Send a simulator run, or one probe event, to a Still Loading receiver.

Examples:
    python3 send_events.py --mode fail --fast --url http://127.0.0.1:8090
    python3 send_events.py --probe --config config.local.json
"""

from __future__ import annotations

import argparse
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

MAC_AGENT = Path(__file__).resolve().parent
ROOT = MAC_AGENT.parent
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(MAC_AGENT))

from messages import ProtocolError, load_local_config, token_is_long_enough  # noqa: E402
from sender import events_for_board, get_job, post_event  # noqa: E402
from simulator import MODES, ManualClock, collect_events, format_timestamp  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send Still Loading events to a local receiver"
    )
    parser.add_argument("--mode", choices=MODES, default="fail")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Kept for familiarity. Sending always uses the fast scenario clock.",
    )
    parser.add_argument("--job-id", default=None)
    parser.add_argument("--url", default=None, help="Receiver base URL, such as http://192.168.1.40:8090")
    parser.add_argument("--token", default=None)
    parser.add_argument(
        "--config",
        default=None,
        help="JSON file with host, port, and token. Defaults to mac-agent/config.local.json when present.",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Send one started event and read it back. Use this for the real board.",
    )
    parser.add_argument(
        "--pace",
        type=float,
        default=0,
        help="Seconds to wait between events. Leave at 0 for the usual fast send.",
    )
    return parser


def resolve_target(args: argparse.Namespace) -> tuple[str, str]:
    """Return (base_url, token) from flags, the environment, or a config file."""
    import os

    config_path = Path(args.config) if args.config else MAC_AGENT / "config.local.json"
    config: dict = {}
    if args.config or config_path.exists():
        config = load_local_config(config_path)

    token = args.token or os.environ.get("STILL_LOADING_TOKEN") or config.get("token")
    if args.url:
        base_url = args.url
    else:
        host = os.environ.get("STILL_LOADING_HOST") or config.get("host")
        port = os.environ.get("STILL_LOADING_PORT") or config.get("port") or 8090
        if not host:
            raise ProtocolError(
                0,
                "missing_target",
                "Pass --url, or set host in config.local.json, or set STILL_LOADING_HOST.",
            )
        base_url = f"http://{host}:{port}"
    if not isinstance(token, str) or not token_is_long_enough(token):
        raise ProtocolError(
            0,
            "short_token",
            "Set a token of at least 16 characters with --token, STILL_LOADING_TOKEN, or config.local.json.",
        )
    return base_url, token.strip()


def probe_event(job_id: str) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "schema_version": 1,
        "event": "started",
        "job_id": job_id,
        "sequence": 1,
        "timestamp": format_timestamp(now),
        "elapsed_seconds": 0,
        "progress": 0,
        "is_failure": False,
        "source": "probe",
    }


def print_result(result: dict) -> None:
    delivery = result["delivery"]
    print(
        f"{delivery:16} {result['event']:12} sequence={result['sequence']} {result['detail']}",
        file=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        base_url, token = resolve_target(args)
    except ProtocolError as exc:
        print(exc.detail, file=sys.stderr)
        print(
            "A connection problem does not mean the job failed. No job was marked failed.",
            file=sys.stderr,
        )
        return 2

    job_id = args.job_id or uuid.uuid4().hex[:8]
    if args.probe:
        events = [probe_event(job_id)]
    else:
        # Sending always uses the scenario clock, so a 20 second story posts immediately.
        events = events_for_board(
            collect_events(args.mode, job_id=job_id, clock=ManualClock(wall_origin=datetime.now(timezone.utc)))
        )

    print(f"Sending {len(events)} event(s) to {base_url}", file=sys.stderr)
    saw_connection_error = False
    for index, event in enumerate(events):
        if index > 0 and args.pace > 0:
            time.sleep(args.pace)
        result = post_event(base_url, token, event)
        print_result(result)
        if result["delivery"] == "connection_error":
            saw_connection_error = True
            print(
                "The receiver did not accept this event. The job was not marked failed.",
                file=sys.stderr,
            )
            return 2
        if result["delivery"] != "accepted":
            return 1

    if args.probe:
        readback = get_job(base_url, token, job_id)
        if readback["delivery"] != "ok":
            print(f"Read-back failed: {readback}", file=sys.stderr)
            return 1
        latest = readback["body"].get("latest", {})
        print("Read back from the receiver:", file=sys.stderr)
        print(
            f"job_id={latest.get('job_id')} event={latest.get('event')} sequence={latest.get('sequence')}",
            file=sys.stderr,
        )
        if latest.get("event") != "started" or latest.get("sequence") != 1:
            print("The receiver stored a different event than the one just sent.", file=sys.stderr)
            return 1
    if saw_connection_error:
        return 2
    print("Delivery finished. This does not light the LEDs.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
