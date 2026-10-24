"""Print simulated Still Loading... job events as JSON lines.

This program stays on the Mac. It does not talk to the Arduino UNO Q.

Examples:
    python3 job_agent.py --mode normal
    python3 job_agent.py --mode fail --fast
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from simulator import MODES, ManualClock, SystemClock, new_job_id, run_scenario


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Still Loading... heartbeat simulator"
    )
    parser.add_argument(
        "--mode",
        choices=MODES,
        default="normal",
        help=(
            "normal finishes on time, slow reports progress less often, "
            "hang stops heartbeats without failing, fail ends with an error"
        ),
    )
    parser.add_argument(
        "--job-id",
        default=None,
        help="Optional fixed job id. A short random id is used when omitted.",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Print the full scenario immediately instead of waiting about 20 seconds.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    job_id = args.job_id or new_job_id()
    if args.fast:
        clock = ManualClock(wall_origin=datetime.now(timezone.utc))
        pace = "fast (no waiting)"
    else:
        clock = SystemClock()
        pace = "real time"

    print(
        f"Still Loading... simulator | mode={args.mode} | job_id={job_id} | {pace}",
        file=sys.stderr,
    )
    print(
        "Each line on stdout is one JSON event. Heartbeats are separate from progress.",
        file=sys.stderr,
    )

    def emit(event: dict) -> None:
        print(json.dumps(event), flush=True)

    try:
        run_scenario(args.mode, job_id, clock, emit)
    except KeyboardInterrupt:
        print(
            "\nStopped. This only prints simulated events on your Mac.",
            file=sys.stderr,
        )
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
