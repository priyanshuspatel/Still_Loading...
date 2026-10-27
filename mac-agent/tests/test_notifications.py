"""Unit tests for mac-agent/notifications.py."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

MAC_AGENT = Path(__file__).resolve().parent.parent
ROOT = MAC_AGENT.parent
sys.path.insert(0, str(MAC_AGENT))

import notifications  # noqa: E402


class TestNotifications(unittest.TestCase):
    def test_escape_applescript(self) -> None:
        raw = 'Error: "Cannot find module \\path\\to\\file"'
        escaped = notifications._escape_applescript(raw)
        self.assertNotIn('"', escaped.replace('\\"', ""))
        self.assertIn('\\"', escaped)
        self.assertIn("\\\\path", escaped)

    def test_format_duration(self) -> None:
        self.assertEqual(notifications._format_duration(5.2), "5.2s")
        self.assertEqual(notifications._format_duration(45.0), "45.0s")
        self.assertEqual(notifications._format_duration(65.0), "1m 5s")
        self.assertEqual(notifications._format_duration(125.4), "2m 5s")

    @patch("shutil.which", return_value="/usr/bin/osascript")
    def test_is_available_true(self, mock_which: MagicMock) -> None:
        self.assertTrue(notifications.is_available())
        mock_which.assert_called_with("osascript")

    @patch("shutil.which", return_value=None)
    def test_is_available_false(self, mock_which: MagicMock) -> None:
        self.assertFalse(notifications.is_available())

    @patch("notifications.is_available", return_value=False)
    @patch("subprocess.Popen")
    def test_notify_noop_when_unavailable(self, mock_popen: MagicMock, mock_avail: MagicMock) -> None:
        notifications.notify("Title", "Message")
        mock_popen.assert_not_called()

    @patch("notifications.is_available", return_value=True)
    @patch("subprocess.Popen")
    def test_notify_dispatches_osascript(self, mock_popen: MagicMock, mock_avail: MagicMock) -> None:
        notifications.notify("Still Loading...", "Job 123 finished.", "Job Completed")
        # Let the thread execute
        import time
        time.sleep(0.05)
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        self.assertEqual(args[0], "osascript")
        self.assertEqual(args[1], "-e")
        script = args[2]
        self.assertIn('display notification "Job 123 finished."', script)
        self.assertIn('with title "Still Loading..."', script)
        self.assertIn('subtitle "Job Completed"', script)

    @patch("notifications.is_available", return_value=True)
    @patch("subprocess.Popen")
    def test_notify_without_subtitle(self, mock_popen: MagicMock, mock_avail: MagicMock) -> None:
        notifications.notify("Still Loading...", "Job 123 finished.")
        import time
        time.sleep(0.05)
        mock_popen.assert_called_once()
        script = mock_popen.call_args[0][0][2]
        self.assertNotIn("subtitle", script)

    @patch("notifications.notify")
    def test_notify_completed(self, mock_notify: MagicMock) -> None:
        notifications.notify_completed("job-abc", 42.5)
        mock_notify.assert_called_once_with(
            title="Still Loading...",
            subtitle="Job Completed",
            message="Job job-abc finished in 42.5s.",
        )

    @patch("notifications.notify")
    def test_notify_failed_with_summary(self, mock_notify: MagicMock) -> None:
        notifications.notify_failed("job-abc", 75.0, summary="Module not found: react")
        mock_notify.assert_called_once_with(
            title="Still Loading...",
            subtitle="Job Failed",
            message="Job job-abc failed after 1m 15s: Module not found: react",
        )

    @patch("notifications.notify")
    def test_notify_failed_without_summary(self, mock_notify: MagicMock) -> None:
        notifications.notify_failed("job-abc", 12.0)
        mock_notify.assert_called_once_with(
            title="Still Loading...",
            subtitle="Job Failed",
            message="Job job-abc failed after 12.0s.",
        )

    @patch("notifications.notify")
    def test_notify_stall(self, mock_notify: MagicMock) -> None:
        notifications.notify_stall("job-abc")
        mock_notify.assert_called_once_with(
            title="Still Loading...",
            subtitle="Suspected Stall",
            message="Job job-abc heartbeats paused — check process liveness.",
        )

    @patch("notifications.is_available", return_value=True)
    @patch("subprocess.Popen", side_effect=OSError("command failed"))
    def test_worker_handles_oserror(self, mock_popen: MagicMock, mock_avail: MagicMock) -> None:
        # Should not raise exception
        notifications.notify("Title", "Message")
        import time
        time.sleep(0.05)


if __name__ == "__main__":
    unittest.main()
