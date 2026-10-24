"""Watch one real Mac command and print Still Loading events.

Examples:
    python3 run_job.py -- python3 -c "import time; time.sleep(3); print('done')"
    python3 run_job.py --send --config config.local.json -- python3 -c "print('hi')"

Arguments after ``--`` are the program and its arguments. They are not
joined into a shell command. Add ``--send`` only when a receiver is already
running. A delivery problem is printed here and is not turned into ``failed``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MAC_AGENT = Path(__file__).resolve().parent
ROOT = MAC_AGENT.parent
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(MAC_AGENT))

from messages import ProtocolError  # noqa: E402
from runner import run_process  # noqa: E402
from send_events import resolve_target  # noqa: E402
from sender import post_event  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a local command and emit Still Loading job events"
    )
    parser.add_argument("--job-id", default=None)
    parser.add_argument(
        "--heartbeat",
        type=float,
        default=2.0,
        help="Seconds between heartbeats while the command is still running.",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Also POST each event to the receiver in config.local.json or --url.",
    )
    parser.add_argument("--url", default=None)
    parser.add_argument("--token", default=None)
    parser.add_argument("--config", default=None)
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Program and arguments. Put them after -- .",
    )
    return parser


def command_argv(raw: list[str]) -> list[str]:
    if raw and raw[0] == "--":
        raw = raw[1:]
    return raw


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = command_argv(args.command)
    if not command:
        print("Pass a command after -- . Example: python3 run_job.py -- python3 -c \"print(1)\"", file=sys.stderr)
        return 2

    target: tuple[str, str] | None = None
    if args.send:
        try:
            target = resolve_target(args)
        except ProtocolError as exc:
            print(exc.detail, file=sys.stderr)
            return 2

    def emit(event: dict) -> None:
        print(json.dumps(event), flush=True)
        if target is None:
            return
        result = post_event(target[0], target[1], event)
        print(
            f"delivery {result['delivery']} {result['event']} sequence={result['sequence']}",
            file=sys.stderr,
        )

    print(
        "Still Loading... process runner. JSON events are on stdout. "
        "The command's own output is captured and is not printed.",
        file=sys.stderr,
    )
    try:
        record = run_process(
            command,
            heartbeat_interval=args.heartbeat,
            job_id=args.job_id,
            emit=emit,
        )
    except (TypeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 130

    print(
        f"job_id={record.job_id} pid={record.pid} "
        f"elapsed_seconds={record.elapsed_seconds} exit_code={record.exit_code} "
        f"stdout_bytes={len(record.stdout.encode('utf-8'))} "
        f"stderr_bytes={len(record.stderr.encode('utf-8'))}",
        file=sys.stderr,
    )
    return 0 if record.exit_code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
