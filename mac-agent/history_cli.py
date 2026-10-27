#!/usr/bin/env python3
"""Still Loading... CLI History & Analytics Viewer

Query past build and test jobs recorded in the persistent history store.

Usage:
  python3 mac-agent/history_cli.py
  python3 mac-agent/history_cli.py --stats
  python3 mac-agent/history_cli.py --failed
  python3 mac-agent/history_cli.py --limit 10
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import urllib.request
import urllib.error

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SHARED_DIR = os.path.join(_REPO_ROOT, "shared")
for path in (_REPO_ROOT, _SHARED_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from history_store import get_history_store
except ImportError:
    get_history_store = None  # type: ignore

# ANSI Colors
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[38;5;82m"
RED = "\033[38;5;196m"
YELLOW = "\033[38;5;220m"
CYAN = "\033[38;5;51m"
WHITE = "\033[38;5;255m"
GRAY = "\033[38;5;240m"


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:4.1f}s"
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}m {secs:02d}s"


def format_timestamp(epoch: float) -> str:
    try:
        dt = datetime.datetime.fromtimestamp(epoch, tz=datetime.timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return "--"


def print_stats(stats: dict) -> None:
    print(f"\n{CYAN}{BOLD}========================================================")
    print(f" Still Loading... Job Analytics & Metrics")
    print(f"========================================================{RESET}")
    total = stats.get("total_jobs", 0)
    completed = stats.get("completed_count", 0)
    failed = stats.get("failed_count", 0)
    rate = stats.get("success_rate", 0.0)
    avg_dur = stats.get("avg_duration_seconds", 0.0)
    tot_dur = stats.get("total_duration_seconds", 0.0)

    rate_color = GREEN if rate >= 80 else (YELLOW if rate >= 50 else RED)

    print(f" Total Jobs Monitored : {WHITE}{BOLD}{total}{RESET}")
    print(f" Completed (Exit 0)   : {GREEN}{completed}{RESET}")
    print(f" Failed (Non-Zero)    : {RED}{failed}{RESET}")
    print(f" Overall Success Rate : {rate_color}{BOLD}{rate}%{RESET}")
    print(f" Average Duration     : {WHITE}{format_duration(avg_dur)}{RESET}")
    print(f" Cumulative Monitored : {WHITE}{format_duration(tot_dur)}{RESET}")

    cats = stats.get("failure_categories", {})
    if cats:
        print(f"\n{YELLOW}{BOLD} Top Failure Categories:{RESET}")
        for cat, count in cats.items():
            print(f"   • {cat.replace('_', ' ').title():<24} : {RED}{count} run(s){RESET}")
    print(f"{CYAN}========================================================{RESET}\n")


def print_jobs(jobs: list[dict], failed_only: bool = False) -> None:
    title = "RECENT FAILED JOBS" if failed_only else "RECENT MONITORED JOBS"
    print(f"\n{CYAN}{BOLD}========================================================")
    print(f" Still Loading... {title} ({len(jobs)})")
    print(f"========================================================{RESET}")

    if not jobs:
        print(f"  {GRAY}No jobs recorded yet.{RESET}")
        print(f"{CYAN}========================================================{RESET}\n")
        return

    header = f"  {'STATUS':<11} {'JOB ID':<18} {'DURATION':<10} {'EXIT':<6} {'END TIME'}"
    print(f"{BOLD}{header}{RESET}")
    print(f"  {GRAY}{'─' * 70}{RESET}")

    for j in jobs:
        is_fail = j.get("is_failure")
        status_badge = f"{RED}[ FAILED ]{RESET}" if is_fail else f"{GREEN}[   OK   ]{RESET}"
        job_id = j.get("job_id", "unknown")[:16]
        dur = format_duration(float(j.get("duration_seconds", 0.0)))
        exit_code = str(j.get("exit_code", "--"))
        end_time = format_timestamp(float(j.get("end_time", 0.0)))

        print(f"  {status_badge} {job_id:<18} {dur:<10} {exit_code:<6} {end_time}")

        if is_fail and j.get("explanation"):
            expl = j["explanation"]
            cat = expl.get("category", "").replace("_", " ").title()
            summary = expl.get("summary", "")
            sugg = expl.get("suggestion", "")
            print(f"     {RED}↳ Cause:{RESET} {cat} — {summary}")
            if sugg:
                print(f"     {GREEN}↳ Fix  :{RESET} {sugg}")

    print(f"{CYAN}========================================================{RESET}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Query Still Loading... job history")
    parser.add_argument("--stats", action="store_true", help="Print aggregate metrics and stats")
    parser.add_argument("--failed", action="store_true", help="Show failed jobs only")
    parser.add_argument("--limit", type=int, default=20, help="Maximum jobs to display (default: 20)")
    parser.add_argument("--board", type=str, default=None, help="Optional board URL (e.g. http://192.168.1.5:8090)")
    parser.add_argument("--token", type=str, default=None, help="Bearer token for board HTTP queries")
    args = parser.parse_args()

    if args.board:
        # Fetch over HTTP
        token = args.token or os.environ.get("STILL_LOADING_TOKEN", "")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        base = args.board.rstrip("/")

        if args.stats:
            req = urllib.request.Request(f"{base}/v1/history/stats", headers=headers)
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                print_stats(data.get("stats", {}))
        else:
            url = f"{base}/v1/history?limit={args.limit}"
            if args.failed:
                url += "&failed_only=1"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                print_jobs(data.get("jobs", []), failed_only=args.failed)
    else:
        # Query local store
        if get_history_store is None:
            print("Error: HistoryStore not available locally.", file=sys.stderr)
            sys.exit(1)
        store = get_history_store()
        if args.stats:
            stats = store.get_stats()
            print_stats(stats)
        else:
            jobs = store.list_jobs(limit=args.limit, failed_only=args.failed)
            print_jobs(jobs, failed_only=args.failed)


if __name__ == "__main__":
    main()
