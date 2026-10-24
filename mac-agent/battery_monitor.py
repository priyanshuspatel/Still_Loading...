"""Send MacBook battery percentage to the Still Loading... UNO Q receiver.

Examples:
    python3 battery_monitor.py --once --dry-run
    python3 battery_monitor.py --mode battery --config config.local.json
    python3 battery_monitor.py --set-mode auto --config config.local.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

MAC_AGENT = Path(__file__).resolve().parent
ROOT = MAC_AGENT.parent
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(MAC_AGENT))

from battery import BatteryReporter, build_battery_message, read_macos_battery  # noqa: E402
from messages import DISPLAY_MODES, ProtocolError  # noqa: E402
from send_events import resolve_target  # noqa: E402
from sender import post_battery, post_display_mode  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Monitor MacBook battery and send updates to the UNO Q receiver"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=30.0,
        help="Seconds between battery checks. Default 30.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Read and send one battery update, then exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the validated battery JSON locally without contacting the board.",
    )
    parser.add_argument(
        "--mode",
        choices=tuple( sorted(DISPLAY_MODES) ),
        default=None,
        help="Optional display mode to include with battery updates (auto, job, or battery).",
    )
    parser.add_argument(
        "--set-mode",
        choices=tuple( sorted(DISPLAY_MODES) ),
        default=None,
        help="Change the receiver display mode immediately and exit.",
    )
    parser.add_argument(
        "--return-to-battery",
        action="store_true",
        help="When in auto mode, return to battery display after a job completes.",
    )
    parser.add_argument("--url", default=None)
    parser.add_argument("--token", default=None)
    parser.add_argument("--config", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.interval <= 0:
        print("--interval must be greater than 0", file=sys.stderr)
        return 2

    if args.dry_run:
        reading = read_macos_battery()
        if reading is None:
            print("Battery status unavailable on this Mac.", file=sys.stderr)
            return 1
        msg = build_battery_message(
            reading,
            display_mode=args.mode,
            return_to_battery=True if args.return_to_battery else None,
        )
        print(json.dumps(msg), flush=True)
        return 0

    try:
        base_url, token = resolve_target(args)
    except ProtocolError as exc:
        print(exc.detail, file=sys.stderr)
        return 2

    return_flag = True if args.return_to_battery else None

    if args.set_mode is not None:
        result = post_display_mode(
            base_url,
            token,
            args.set_mode,
            return_to_battery=return_flag,
        )
        if not result["delivered"]:
            print(f"Could not set display mode: {result['delivery']}", file=sys.stderr)
            return 1
        lights = result["body"].get("lights", {})
        print(
            f"display_mode={args.set_mode} state={lights.get('state')} code={lights.get('code')}",
            flush=True,
        )
        return 0

    if args.mode == "battery":
        # Switch the board to battery mode immediately so it shows '--' if no reading is ready.
        post_display_mode(
            base_url,
            token,
            "battery",
            return_to_battery=return_flag,
        )

    reporter = BatteryReporter(
        lambda msg: post_battery(base_url, token, msg),
        display_mode=args.mode,
        return_to_battery=return_flag,
    )

    try:
        while True:
            outcome = reporter.poll_once()
            status = outcome["status"]
            reading = outcome["reading"]
            if status == "sent" and reading is not None:
                print(
                    f"battery {reading.percent}% ({reading.charging_state}) -> accepted",
                    flush=True,
                )
            elif status == "unavailable":
                print("battery unavailable; nothing sent", file=sys.stderr)
            elif status == "delivery_failed":
                delivery = outcome.get("delivery", {})
                print(
                    f"battery delivery {delivery.get('delivery')}: {delivery.get('detail')}",
                    file=sys.stderr,
                )
            if args.once:
                return 0 if status in {"sent", "unchanged"} else 1
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nBattery monitor stopped.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
