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
import os
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
import audio  # noqa: E402
import notifications  # noqa: E402


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
        "--no-excerpt",
        action="store_true",
        help="Do not attach a failure log excerpt to the failed event.",
    )
    parser.add_argument(
        "--gemma",
        action="store_true",
        help=(
            "After a failure, ask the configured Gemma endpoint to explain the redacted log. "
            "The rules explainer is used if Gemma times out or returns unverifiable output. "
            "Same as GEMMA_ENABLED=1."
        ),
    )
    parser.add_argument(
        "--bell",
        action="store_true",
        help=(
            "Play a macOS system sound on completion or failure. "
            "Requires afplay (available by default on macOS). "
            "Glass.aiff plays on success; Basso.aiff plays on failure; "
            "Tink.aiff plays twice when a suspected stall is detected."
        ),
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help=(
            "Display a native macOS Notification Center banner on completion or failure. "
            "Requires osascript (available by default on macOS)."
        ),
    )
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
    if args.gemma:
        os.environ["GEMMA_ENABLED"] = "1"
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
            include_excerpt=not args.no_excerpt,
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
    if record.exit_code != 0:
        failed_event = next((e for e in reversed(record.events) if e.get("event") == "failed"), None)
        if failed_event and "explanation" in failed_event:
            exp = failed_event["explanation"]
            status = exp.get("verification_status")
            status_line = f"\n                      Gemma status: {status}" if status else ""
            print(
                f"[Failure Explanation] ({exp.get('category')}): {exp.get('summary')}\n"
                f"                      Suggestion: {exp.get('suggestion')}"
                f"{status_line}",
                file=sys.stderr,
            )

    # Ambient audio cue — only when --bell is requested
    if args.bell:
        if not audio.is_available():
            print(
                "[audio] --bell requested but afplay is not available on this platform.",
                file=sys.stderr,
            )
        elif record.exit_code == 0:
            audio.play_completed()
        else:
            audio.play_failed()

    # Native desktop notification — only when --notify is requested
    if args.notify:
        if not notifications.is_available():
            print(
                "[notify] --notify requested but osascript is not available on this platform.",
                file=sys.stderr,
            )
        elif record.exit_code == 0:
            notifications.notify_completed(record.job_id, record.elapsed_seconds)
        else:
            summary = None
            failed_event = next((e for e in reversed(record.events) if e.get("event") == "failed"), None)
            if failed_event and "explanation" in failed_event:
                summary = failed_event["explanation"].get("summary")
            notifications.notify_failed(record.job_id, record.elapsed_seconds, summary=summary)

    return 0 if record.exit_code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
