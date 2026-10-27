"""Unit tests for mac-agent/audio.py.

These tests must run on any platform (including Linux CI) without
``afplay`` present and without any macOS-specific setup.  Every test
patches the internals so no actual sound is ever played and no
subprocesses are spawned.
"""

from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

# ---------------------------------------------------------------------------
# Path setup — identical to other test files in this suite
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "mac-agent"))

import audio  # noqa: E402


class TestIsAvailable(unittest.TestCase):
    """audio.is_available() should reflect whether afplay is on PATH."""

    def test_returns_true_when_afplay_found(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/afplay"):
            self.assertTrue(audio.is_available())

    def test_returns_false_when_afplay_missing(self) -> None:
        with patch("shutil.which", return_value=None):
            self.assertFalse(audio.is_available())


class TestPlayAsync(unittest.TestCase):
    """_play_async() must not block and must not raise on any platform."""

    def test_returns_silently_when_afplay_unavailable(self) -> None:
        """No Popen call when afplay is absent."""
        with patch("audio.is_available", return_value=False), \
             patch("subprocess.Popen") as mock_popen:
            audio._play_async(Path("/System/Library/Sounds/Glass.aiff"))
            mock_popen.assert_not_called()

    def test_returns_silently_when_file_missing(self) -> None:
        """No Popen call when the sound file does not exist."""
        with patch("audio.is_available", return_value=True), \
             patch("subprocess.Popen") as mock_popen, \
             patch.object(Path, "exists", return_value=False):
            audio._play_async(Path("/nonexistent/sound.aiff"))
            mock_popen.assert_not_called()

    def test_spawns_popen_on_happy_path(self) -> None:
        """Popen is called once when afplay is available and file exists."""
        with patch("audio.is_available", return_value=True), \
             patch.object(Path, "exists", return_value=True), \
             patch("subprocess.Popen") as mock_popen:
            # Run synchronously to avoid thread-timing issues in tests
            audio._play_async(Path("/System/Library/Sounds/Glass.aiff"), repeat=1)

            # Give the daemon thread a moment to call Popen
            import time
            time.sleep(0.05)
            mock_popen.assert_called_once()
            cmd = mock_popen.call_args[0][0]
            self.assertEqual(cmd[0], "afplay")
            self.assertIn("Glass.aiff", cmd[1])

    def test_spawns_popen_repeat_times(self) -> None:
        """Popen is called `repeat` times for stall cue (repeat=2)."""
        with patch("audio.is_available", return_value=True), \
             patch.object(Path, "exists", return_value=True), \
             patch("subprocess.Popen") as mock_popen:
            audio._play_async(Path("/System/Library/Sounds/Tink.aiff"), repeat=2)

            import time
            time.sleep(0.1)
            self.assertEqual(mock_popen.call_count, 2)

    def test_daemon_thread_is_used(self) -> None:
        """The spawned thread must be a daemon so it never blocks shutdown."""
        threads_created: list[threading.Thread] = []
        original_start = threading.Thread.start

        def capture_thread(self_thread: threading.Thread, *a, **kw):  # type: ignore[override]
            threads_created.append(self_thread)
            original_start(self_thread, *a, **kw)

        with patch("audio.is_available", return_value=True), \
             patch.object(Path, "exists", return_value=True), \
             patch("subprocess.Popen"), \
             patch.object(threading.Thread, "start", capture_thread):
            audio._play_async(Path("/System/Library/Sounds/Glass.aiff"))

        self.assertTrue(len(threads_created) > 0)
        for t in threads_created:
            self.assertTrue(t.daemon, "Audio thread must be a daemon thread")


class TestPublicCues(unittest.TestCase):
    """play_completed / play_failed / play_stall delegate to play_cue."""

    def _assert_cue_called(self, fn, expected_name: str) -> None:
        with patch("audio.play_cue") as mock_cue:
            fn()
            mock_cue.assert_called_once_with(expected_name)

    def test_play_completed_calls_cue(self) -> None:
        self._assert_cue_called(audio.play_completed, "completed")

    def test_play_failed_calls_cue(self) -> None:
        self._assert_cue_called(audio.play_failed, "failed")

    def test_play_stall_calls_cue(self) -> None:
        self._assert_cue_called(audio.play_stall, "stall")


class TestPlayCue(unittest.TestCase):
    """play_cue(name) dispatches to _play_async with correct paths."""

    def test_known_cues_call_play_async(self) -> None:
        for name in ("completed", "failed", "stall"):
            with self.subTest(name=name), \
                 patch("audio._play_async") as mock_async:
                audio.play_cue(name)
                mock_async.assert_called_once()
                path_arg = mock_async.call_args[0][0]
                self.assertIsInstance(path_arg, Path)
                # Each cue must reference a real filename suffix
                self.assertTrue(str(path_arg).endswith(".aiff"),
                                f"Expected .aiff path, got {path_arg}")

    def test_unknown_cue_is_silent(self) -> None:
        """Unknown cue names must not raise."""
        with patch("audio._play_async") as mock_async:
            audio.play_cue("nonexistent_cue")  # type: ignore[arg-type]
            mock_async.assert_not_called()

    def test_stall_repeat_is_two(self) -> None:
        """Stall cue must be scheduled with repeat=2."""
        with patch("audio._play_async") as mock_async:
            audio.play_cue("stall")
            _, kwargs_or_args = mock_async.call_args[0], mock_async.call_args
            repeat = mock_async.call_args[0][1] if len(mock_async.call_args[0]) > 1 \
                else mock_async.call_args[1].get("repeat", 1)
            self.assertEqual(repeat, 2)

    def test_completed_repeat_is_one(self) -> None:
        """Completed cue must be scheduled with repeat=1."""
        with patch("audio._play_async") as mock_async:
            audio.play_cue("completed")
            repeat = mock_async.call_args[0][1] if len(mock_async.call_args[0]) > 1 \
                else mock_async.call_args[1].get("repeat", 1)
            self.assertEqual(repeat, 1)


if __name__ == "__main__":
    unittest.main()
