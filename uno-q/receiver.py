"""Run the Still Loading receiver on the UNO Q Linux side, or on the Mac for a local test.

This process listens on the network. It does not flash the microcontroller.
When a light state changes it prints a line. App Lab reads that state
with GET /v1/lights on this same port, using the same bearer token.
A status file under /tmp is only a local note. App Lab does not read it.
Port 8090 and the token check are unchanged.

    export STILL_LOADING_TOKEN='paste-the-same-token-you-put-on-the-mac'
    python3 uno-q/receiver.py --host 0.0.0.0 --port 8090

On the Mac, for a loopback test, bind to 127.0.0.1 instead of 0.0.0.0.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))

from http_api import serve  # noqa: E402
from lights import LightPublisher  # noqa: E402
from messages import ProtocolError, load_local_config, token_is_long_enough  # noqa: E402
from state_engine import EngineConfig, StateEngine  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Still Loading... network receiver")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--token", default=None)
    parser.add_argument("--config", default=None)
    parser.add_argument(
        "--heartbeat-timeout",
        type=float,
        default=6.0,
        help="Seconds without a heartbeat before suspected_stall. Default 6.",
    )
    parser.add_argument(
        "--slow-gap",
        type=float,
        default=6.0,
        help="Seconds between progress events before the slow state. Default 6.",
    )
    parser.add_argument(
        "--lights-file",
        default="/tmp/still-loading-lights.json",
        help="Small status file the App Lab companion reads. It has no token.",
    )
    return parser


def chosen_token(args: argparse.Namespace) -> str:
    if args.token:
        return args.token.strip()
    env_token = os.environ.get("STILL_LOADING_TOKEN")
    if env_token:
        return env_token.strip()
    config_path = Path(args.config) if args.config else Path("config.local.json")
    if config_path.exists():
        config = load_local_config(config_path)
        token = config.get("token")
        if isinstance(token, str):
            return token.strip()
    raise ProtocolError(
        0,
        "short_token",
        "Set STILL_LOADING_TOKEN, pass --token, or put token in config.local.json.",
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        token = chosen_token(args)
        if not token_is_long_enough(token):
            raise ProtocolError(
                0,
                "short_token",
                "The token must be at least 16 characters.",
            )
        publisher = LightPublisher(Path(args.lights_file))
        engine = StateEngine(
            EngineConfig(
                heartbeat_timeout_s=args.heartbeat_timeout,
                slow_progress_gap_s=args.slow_gap,
            ),
            on_change=publisher.show,
        )
        serve(args.host, args.port, token, announce=True, engine=engine)
    except ProtocolError as exc:
        print(exc.detail, file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Could not listen on {args.host}:{args.port}. {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
