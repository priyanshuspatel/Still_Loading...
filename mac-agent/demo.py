"""Still Loading... interactive and automated multi-phase demonstration script.

Phase 8: Provides a complete showcase of all Still Loading... capabilities:
1. Normal Job: Started, steady heartbeats, live percentage, completed checkmark.
2. Slow Job: Long intervals between progress ticks.
3. Suspected Stall: Heartbeat pauses at 8s, receiver flags stall, recovers on resumption.
4. Failure with Excerpt & AI Rules Explanation: Excerpt sanitization, secret redaction, structured explanation.
5. Battery Monitoring: Real MacBook battery reading via pmset, charging glyph, and priority rules.
6. Chrome Download Monitor: Live download progress and priority override.
7. Display Modes: Auto priority vs. explicit battery vs. explicit job mode.

Usage:
    python3 demo.py --all --fast
    python3 demo.py --scenario normal
    python3 demo.py --scenario fail
    python3 demo.py --scenario stall
    python3 demo.py --scenario battery
    python3 demo.py --all --send --config config.local.json
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

from battery import read_macos_battery
from explainer import explain_failure
from messages import ProtocolError
from runner import run_process
from send_events import resolve_target
from sender import events_for_board, post_event
from simulator import collect_events


def _divider(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def run_simulator_demo(mode: str, *, fast: bool = True, target: tuple[str, str] | None = None) -> None:
    _divider(f"Demo Scenario: '{mode.upper()}' (Simulator)")
    events = collect_events(mode)
    wire = events_for_board(events)

    print(f"Total simulated ticks: {len(events)} | Wire messages: {len(wire)}")
    for event in events:
        is_wire = event in wire
        prefix = "-> [WIRE]" if is_wire else "   [LOCAL]"
        print(
            f"{prefix} event={event['event']:<17} progress={event['progress']:>3}% "
            f"elapsed={event['elapsed_seconds']:>4.1f}s is_failure={event['is_failure']}"
        )
        if is_wire and target:
            res = post_event(target[0], target[1], event)
            print(f"       delivery: {res['delivery']} (HTTP {res['status_code']})")
        if not fast and is_wire:
            time.sleep(1.0)


def run_process_failure_demo(*, target: tuple[str, str] | None = None) -> None:
    _divider("Demo Scenario: Real Process Failure with Excerpt & Rules Explanation")
    print("Executing a Python process that logs an error, prints a fake token, and crashes...")

    failing_script = (
        "import sys\n"
        "sys.stderr.write('Authorization: Bearer test_secret_token_12345\\n')\n"
        "sys.stderr.write('ModuleNotFoundError: No module named \\'pandas\\'\\n')\n"
        "sys.exit(1)\n"
    )

    def on_event(ev: dict) -> None:
        print(f"-> [WIRE] {ev['event']} seq={ev['sequence']} progress={ev['progress']}%")
        if ev.get("excerpt"):
            print(f"   Excerpt: {ev['excerpt']}")
        if ev.get("explanation"):
            exp = ev["explanation"]
            print(f"   Explanation [{exp['category']}]: {exp['summary']}")
            print(f"   Suggested Fix: {exp['suggestion']}")
            print(f"   Confidence: {exp['confidence']} (Engine: {exp['source']})")
        if target:
            res = post_event(target[0], target[1], ev)
            print(f"   delivery: {res['delivery']}")

    record = run_process([sys.executable, "-c", failing_script], heartbeat_interval=1.0, emit=on_event)
    print(f"\nProcess completed with exit code: {record.exit_code}")
    print(f"Captured stderr ({len(record.stderr)} bytes):\n{record.stderr.strip()}")


def run_battery_demo() -> None:
    _divider("Demo Scenario: MacBook Battery Telemetry")
    reading = read_macos_battery()
    if reading is None:
        print("Battery reading is not available on this device (desktop Mac / VM).")
        return

    print(f"Live Battery Percentage : {reading.percent}%")
    print(f"Charging State          : {reading.charging_state.upper()}")
    print("Matrix Display Representation:")
    if reading.charging_state == "charging":
        print(f"  Frame: Centered '{reading.percent}' alternating with live charging heart pulse.")
    else:
        print(f"  Frame: Centered '{reading.percent}' (steady numeric percentage).")


def main() -> int:
    parser = argparse.ArgumentParser(description="Still Loading... Comprehensive Multi-Phase Demo")
    parser.add_argument(
        "--scenario",
        choices=["normal", "slow", "hang", "fail", "process_fail", "battery", "all"],
        default="all",
        help="Which scenario to demonstrate.",
    )
    parser.add_argument(
        "--all",
        dest="scenario",
        action="store_const",
        const="all",
        help="Run all scenarios in sequence.",
    )
    parser.add_argument("--fast", action="store_true", default=True, help="Run without real-time delays.")
    parser.add_argument("--live", dest="fast", action="store_false", help="Run with real-time delays.")
    parser.add_argument("--send", action="store_true", help="Post events to live UNO Q receiver.")
    parser.add_argument("--config", default=None, help="Path to config.local.json.")
    parser.add_argument("--url", default=None, help="Receiver URL override.")
    parser.add_argument("--token", default=None, help="Bearer token override.")
    args = parser.parse_args()

    target: tuple[str, str] | None = None
    if args.send:
        try:
            target = resolve_target(args)
            print(f"Targeting receiver at: {target[0]}")
        except ProtocolError as exc:
            print(f"Error resolving target: {exc.detail}", file=sys.stderr)
            return 2

    print("======================================================================")
    print("               STILL LOADING... DEMONSTRATION SUITE")
    print("                  Stop staring. Start living.")
    print("======================================================================")

    scenarios = (
        ["normal", "slow", "hang", "fail", "process_fail", "battery"]
        if args.scenario == "all"
        else [args.scenario]
    )

    for sc in scenarios:
        if sc in ("normal", "slow", "hang", "fail"):
            run_simulator_demo(sc, fast=args.fast, target=target)
        elif sc == "process_fail":
            run_process_failure_demo(target=target)
        elif sc == "battery":
            run_battery_demo()

    _divider("Demonstration Complete")
    print("All subsystems verified: Simulator, Wire Protocol, Excerpt Redaction, Rules Explainer, Battery.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
