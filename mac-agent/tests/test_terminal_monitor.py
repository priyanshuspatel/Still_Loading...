"""Unit tests for mac-agent/terminal_monitor.py."""

from __future__ import annotations

import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "mac-agent"))

from terminal_monitor import (
    TerminalDashboard,
    format_bytes,
    render_progress_bar,
    LED_CHARS,
)


class TerminalMonitorTests(unittest.TestCase):
    def test_format_bytes(self) -> None:
        self.assertEqual(format_bytes(None), "--")
        self.assertEqual(format_bytes(512), "512.0 B")
        self.assertEqual(format_bytes(1024), "1.0 KB")
        self.assertEqual(format_bytes(1024 * 1024 * 5), "5.0 MB")
        self.assertEqual(format_bytes(1024 * 1024 * 1024 * 2), "2.0 GB")

    def test_render_progress_bar(self) -> None:
        bar0 = render_progress_bar(0, width=10)
        self.assertIn("0%", bar0)
        bar50 = render_progress_bar(50, width=10)
        self.assertIn("50%", bar50)
        bar100 = render_progress_bar(100, width=10)
        self.assertIn("100%", bar100)

    def test_led_chars_has_all_brightness_levels(self) -> None:
        for level in range(8):
            self.assertIn(level, LED_CHARS)

    def test_dashboard_demo_cycle_and_render(self) -> None:
        dashboard = TerminalDashboard(mode="demo")
        dashboard.cycle_demo_state()

        # Capture rendered frame
        stdout_capture = io.StringIO()
        with patch.object(sys, "stdout", stdout_capture):
            dashboard.render()

        rendered = stdout_capture.getvalue()
        self.assertIn("STILL LOADING... TERMINAL MONITOR", rendered)
        self.assertIn("PHYSICAL MATRIX TWIN (8×13)", rendered)
        self.assertIn("SYSTEM & TELEMETRY STATUS", rendered)

    def test_dashboard_failure_rendering(self) -> None:
        dashboard = TerminalDashboard(mode="demo")
        dashboard.state = "failed"
        dashboard.exit_code = 1
        dashboard.failure_explanation = {
            "category": "syntax_error",
            "summary": "SyntaxError in script",
            "suggestion": "Check line 42 for missing colon",
        }
        dashboard.failure_excerpt = "SyntaxError: invalid syntax"

        stdout_capture = io.StringIO()
        with patch.object(sys, "stdout", stdout_capture):
            dashboard.render()

        rendered = stdout_capture.getvalue()
        self.assertIn("FAILURE INTELLIGENCE", rendered)
        self.assertIn("SYNTAX_ERROR", rendered)
        self.assertIn("Check line 42", rendered)


if __name__ == "__main__":
    unittest.main()
