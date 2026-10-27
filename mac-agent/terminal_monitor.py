#!/usr/bin/env python3
"""Still Loading... Terminal Monitor & Live Matrix Twin

A zero-dependency, self-refreshing ANSI terminal companion for long-running jobs.
Renders the Arduino UNO Q 8x13 blue LED matrix, MacBook battery gauge, Chrome
download monitor, and Failure Intelligence directly in your terminal.

Usage:
  python3 mac-agent/terminal_monitor.py --demo
  python3 mac-agent/terminal_monitor.py --relay http://127.0.0.1:8765
  python3 mac-agent/terminal_monitor.py --board http://192.168.1.5:8090 --token <SECRET>
"""

from __future__ import annotations

import argparse
import json
import math
import os
import signal
import sys
import time
import urllib.error
import urllib.request
from typing import Any

# Add repo root and shared directory to sys.path
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SHARED_DIR = os.path.join(_REPO_ROOT, "shared")
for path in (_REPO_ROOT, _SHARED_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from matrix_display import COLS, ROWS, select_display_frame
except ImportError:
    ROWS, COLS = 8, 13

    def select_display_frame(state: str, progress: int = 0, elapsed_ms: int = 0, **kw):
        return ("placeholder", [[0] * COLS for _ in range(ROWS)])


# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
BLUE = "\033[38;5;39m"
BRIGHT_BLUE = "\033[38;5;45m"
CYAN = "\033[38;5;51m"
GREEN = "\033[38;5;82m"
YELLOW = "\033[38;5;220m"
ORANGE = "\033[38;5;208m"
RED = "\033[38;5;196m"
WHITE = "\033[38;5;255m"
GRAY = "\033[38;5;240m"
DARK_GRAY = "\033[38;5;236m"
BG_DARK = "\033[48;5;234m"

# LED Matrix Grayscale glyph mapping (brightness 0..7)
LED_CHARS = {
    0: f"{DARK_GRAY}·{RESET}",
    1: f"{BLUE}░{RESET}",
    2: f"{BLUE}▒{RESET}",
    3: f"{CYAN}▒{RESET}",
    4: f"{CYAN}▓{RESET}",
    5: f"{BRIGHT_BLUE}█{RESET}",
    6: f"{BRIGHT_BLUE}█{RESET}",
    7: f"{WHITE}█{RESET}",
}


def clear_screen() -> None:
    sys.stdout.write("\033[H\033[2J")
    sys.stdout.flush()


def hide_cursor() -> None:
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()


def show_cursor() -> None:
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()


def format_bytes(num_bytes: int | float | None) -> str:
    if num_bytes is None or num_bytes < 0:
        return "--"
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} TB"


def render_progress_bar(percent: int | float, width: int = 24, fill_char: str = "━", empty_char: str = "━") -> str:
    clamped = max(0.0, min(100.0, float(percent)))
    fill_len = int(round((clamped / 100.0) * width))
    empty_len = width - fill_len
    return f"{CYAN}{fill_char * fill_len}{GRAY}{empty_char * empty_len}{RESET} {clamped:3.0f}%"


class TerminalDashboard:
    def __init__(
        self,
        mode: str = "demo",
        relay_url: str | None = None,
        board_url: str | None = None,
        token: str | None = None,
        poll_interval: float = 0.25,
    ) -> None:
        self.mode = mode
        self.relay_url = relay_url.rstrip("/") if relay_url else None
        self.board_url = board_url.rstrip("/") if board_url else None
        self.token = token
        self.poll_interval = poll_interval
        self.start_time = time.time()
        self.demo_index = 0
        self.demo_timer = time.time()

        # Telemetry State
        self.state = "idle"
        self.job_id = "job-demo-01"
        self.progress = 0
        self.progress_known = False
        self.sequence = 0
        self.battery_pct = 78
        self.charging_state = "discharging"
        self.download_active = False
        self.download_progress = 0
        self.download_speed = 0
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.failure_explanation: dict[str, Any] | None = None
        self.failure_excerpt: str | None = None
        self.exit_code: int | None = None

    def fetch_from_relay(self) -> None:
        if not self.relay_url:
            return
        req = urllib.request.Request(f"{self.relay_url}/api/telemetry")
        try:
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                lights = data.get("lights", {})
                self.state = lights.get("state", "idle")
                self.progress = lights.get("progress", 0)
                self.progress_known = lights.get("progress_known", False)
                self.sequence = lights.get("sequence", 0)
                self.job_id = lights.get("job_id") or "none"

                battery = data.get("battery", {})
                self.battery_pct = battery.get("percent") or 0
                self.charging_state = battery.get("charging_state") or "unknown"

                download = data.get("download", {})
                self.download_active = download.get("active", False)
                self.download_progress = download.get("progress", 0)
                self.download_speed = download.get("speed_bytes_sec", 0)
                self.downloaded_bytes = download.get("downloaded_bytes", 0)
                self.total_bytes = download.get("total_bytes", 0)

                job = data.get("job")
                if job:
                    self.failure_explanation = job.get("explanation")
                    self.failure_excerpt = job.get("excerpt")
                    self.exit_code = job.get("exit_code")
                else:
                    self.failure_explanation = None
                    self.failure_excerpt = None
        except Exception:
            pass

    def cycle_demo_state(self) -> None:
        now = time.time()
        elapsed_demo = now - self.demo_timer

        # Cycle scenarios every 8 seconds
        presets = [
            ("running", 35, True, False, None),
            ("slow", 60, True, False, None),
            ("suspected_stall", 60, True, False, None),
            (
                "failed",
                60,
                True,
                False,
                {
                    "explanation": {
                        "category": "missing_dependency",
                        "summary": "Missing Python module: 'pandas'",
                        "suggestion": "pip install pandas",
                    },
                    "excerpt": "Authorization: [REDACTED]\nModuleNotFoundError: No module named 'pandas'",
                    "exit_code": 1,
                },
            ),
            ("completed", 100, True, False, None),
            ("battery", 84, True, False, None),
            ("battery_charging", 46, True, False, None),
            ("download", 72, True, True, None),
        ]

        preset_idx = int(elapsed_demo // 6) % len(presets)
        p_state, p_prog, p_known, p_dl, p_fail = presets[preset_idx]

        self.state = p_state
        self.progress = p_prog
        self.progress_known = p_known
        self.download_active = p_dl
        if p_dl:
            self.download_progress = 72
            self.download_speed = 3450000
            self.downloaded_bytes = 420000000
            self.total_bytes = 580000000
        else:
            self.download_progress = 0

        if p_fail:
            self.failure_explanation = p_fail["explanation"]
            self.failure_excerpt = p_fail["excerpt"]
            self.exit_code = p_fail["exit_code"]
        else:
            self.failure_explanation = None
            self.failure_excerpt = None
            self.exit_code = None

    def render(self) -> None:
        elapsed_ms = int((time.time() - self.start_time) * 1000)

        # Get 8x13 LED matrix frame
        frame_kind, frame = select_display_frame(
            self.state,
            progress=self.progress,
            elapsed_ms=elapsed_ms,
            progress_known=self.progress_known,
        )

        # Render matrix rows
        matrix_lines = []
        for r in range(ROWS):
            row_str = " ".join(LED_CHARS[frame[r][c]] for c in range(COLS))
            matrix_lines.append(f"  │  {row_str}  │")

        # Status badge color
        state_badge = self.state.upper().replace("_", " ")
        if self.state in ("running", "completed"):
            badge_color = GREEN
        elif self.state in ("slow", "battery_charging"):
            badge_color = YELLOW
        elif self.state in ("suspected_stall", "failed"):
            badge_color = RED
        elif self.state == "download":
            badge_color = CYAN
        else:
            badge_color = BLUE

        out = []
        out.append(f"\033[H")  # Move to top-left
        out.append(f"{CYAN}{BOLD}┌────────────────────────────────────────────────────────────────────────┐{RESET}")
        out.append(f"{CYAN}{BOLD}│  STILL LOADING... TERMINAL MONITOR         Stop staring. Start living. │{RESET}")
        out.append(f"{CYAN}{BOLD}└────────────────────────────────────────────────────────────────────────┘{RESET}")
        out.append("")

        # Two-column layout: Left = Matrix Twin, Right = Status & Gauges
        out.append(f"  {BOLD}PHYSICAL MATRIX TWIN (8×13){RESET}         {BOLD}SYSTEM & TELEMETRY STATUS{RESET}")
        out.append(f"  ┌─────────────────────────────┐        State: {badge_color}{BOLD}[ {state_badge} ]{RESET}")

        # Lines 1 - 8
        m0 = matrix_lines[0]
        out.append(f"{m0}        Job ID    : {WHITE}{self.job_id}{RESET}")

        m1 = matrix_lines[1]
        out.append(f"{m1}        Progress  : {render_progress_bar(self.progress)}")

        m2 = matrix_lines[2]
        chg_glyph = "⚡ " if self.charging_state == "charging" else "🔋 "
        out.append(f"{m2}        Battery   : {render_progress_bar(self.battery_pct, 16)} {chg_glyph}{self.charging_state}")

        m3 = matrix_lines[3]
        dl_status = f"{render_progress_bar(self.download_progress, 16)} ({format_bytes(self.download_speed)}/s)" if self.download_active else f"{GRAY}Idle / No active downloads{RESET}"
        out.append(f"{m3}        Download  : {dl_status}")

        m4 = matrix_lines[4]
        out.append(f"{m4}        Frame     : {DIM}{frame_kind}{RESET}")

        m5 = matrix_lines[5]
        out.append(f"{m5}        Mode      : {DIM}{self.mode.upper()}{RESET}")

        m6 = matrix_lines[6]
        out.append(f"{m6}        Elapsed   : {DIM}{elapsed_ms // 1000}s{RESET}")

        m7 = matrix_lines[7]
        out.append(f"{m7}        Sequence  : {DIM}#{self.sequence}{RESET}")

        out.append(f"  └─────────────────────────────┘")
        out.append("")

        # Failure Intelligence Box (if present or in failed state)
        if self.state == "failed" or self.failure_explanation:
            out.append(f"  {RED}{BOLD}┌─ FAILURE INTELLIGENCE & RESOLUTION ─────────────────────────────────┐{RESET}")
            if self.failure_explanation:
                cat = self.failure_explanation.get("category", "error").upper()
                summary = self.failure_explanation.get("summary", "Process failed.")
                suggestion = self.failure_explanation.get("suggestion", "")
                out.append(f"  {RED}│{RESET}  {RED}{BOLD}Category  :{RESET} {YELLOW}{cat}{RESET} (Exit Code: {self.exit_code or 1})")
                out.append(f"  {RED}│{RESET}  {RED}{BOLD}Diagnosis :{RESET} {WHITE}{summary}{RESET}")
                if suggestion:
                    out.append(f"  {RED}│{RESET}  {GREEN}{BOLD}Fix Action:{RESET} {GREEN}{suggestion}{RESET}")
            if self.failure_excerpt:
                out.append(f"  {RED}│{RESET}  {GRAY}Log Excerpt (Secrets Redacted):{RESET}")
                for line in self.failure_excerpt.strip().split("\n")[:4]:
                    out.append(f"  {RED}│{RESET}    {DIM}{line[:65]}{RESET}")
            out.append(f"  {RED}{BOLD}└─────────────────────────────────────────────────────────────────────┘{RESET}")
            out.append("")

        out.append(f"{GRAY}Press Ctrl+C to exit terminal monitor.{RESET}")
        sys.stdout.write("\n".join(out) + "\n")
        sys.stdout.flush()

    def run(self) -> None:
        hide_cursor()
        clear_screen()
        try:
            while True:
                if self.mode == "relay":
                    self.fetch_from_relay()
                else:
                    self.cycle_demo_state()

                self.render()
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            pass
        finally:
            show_cursor()
            sys.stdout.write("\nExited Terminal Monitor cleanly.\n")
            sys.stdout.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description="Still Loading... Live Terminal Monitor")
    parser.add_argument("--demo", action="store_true", default=True, help="Run interactive state audition demo")
    parser.add_argument("--relay", type=str, default=None, help="Connect to local telemetry relay URL (e.g. http://127.0.0.1:8765)")
    parser.add_argument("--board", type=str, default=None, help="Connect directly to UNO Q board URL (e.g. http://192.168.1.5:8090)")
    parser.add_argument("--token", type=str, default=None, help="Bearer token for board authentication")
    parser.add_argument("--interval", type=float, default=0.25, help="Refresh interval in seconds (default: 0.25)")
    args = parser.parse_args()

    mode = "relay" if args.relay else "demo"
    dashboard = TerminalDashboard(
        mode=mode,
        relay_url=args.relay,
        board_url=args.board,
        token=args.token,
        poll_interval=args.interval,
    )
    dashboard.run()


if __name__ == "__main__":
    main()
