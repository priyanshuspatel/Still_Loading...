"""Ambient audio cues for Still Loading job events.

Plays short, tasteful system sounds on macOS using ``afplay`` so the user
gets an audible signal without staring at the screen.  All playback is
non-blocking; the calling thread is never delayed by a sound.

Sounds chosen from /System/Library/Sounds/ for their semantic fit:
    completed → Glass.aiff   — clean, positive chime
    failed    → Basso.aiff   — low, attention-drawing thud
    stall     → Tink.aiff    — gentle, neutral tap (repeated twice)

The module works only on macOS where ``afplay`` is available.  On other
platforms every public function silently becomes a no-op so tests can run
cross-platform without patching.

Public API
----------
play_completed() → None
play_failed()    → None
play_stall()     → None
play_cue(name)   → None    name ∈ {'completed', 'failed', 'stall'}
is_available()   → bool    True if afplay is on PATH
"""

from __future__ import annotations

import shutil
import subprocess
import threading
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Sound file paths
# ---------------------------------------------------------------------------

_SOUNDS_DIR = Path("/System/Library/Sounds")

_CUE_PATHS: dict[str, Path] = {
    "completed": _SOUNDS_DIR / "Glass.aiff",
    "failed": _SOUNDS_DIR / "Basso.aiff",
    "stall": _SOUNDS_DIR / "Tink.aiff",
}

# Number of times to play each cue (stall plays twice to be distinct)
_CUE_REPEAT: dict[str, int] = {
    "completed": 1,
    "failed": 1,
    "stall": 2,
}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def is_available() -> bool:
    """Return True if ``afplay`` is on PATH and we are on macOS."""
    return shutil.which("afplay") is not None


def _play_async(sound_path: Path, repeat: int = 1) -> None:
    """Spawn ``afplay`` in a daemon thread so the caller never blocks.

    If ``afplay`` is not available or the sound file does not exist the
    function returns silently without raising.
    """
    if not is_available():
        return
    if not sound_path.exists():
        return

    def _worker() -> None:
        for _ in range(max(1, repeat)):
            try:
                subprocess.Popen(
                    ["afplay", str(sound_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except OSError:
                # afplay disappeared or permission denied — ignore gracefully
                break

    thread = threading.Thread(target=_worker, daemon=True, name="still-loading-audio")
    thread.start()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def play_cue(name: str) -> None:
    """Play a named ambient cue non-blocking.

    Parameters
    ----------
    name:
        One of ``'completed'``, ``'failed'``, or ``'stall'``.  Unknown names
        are silently ignored so callers do not need to guard every call site.
    """
    path: Optional[Path] = _CUE_PATHS.get(name)
    if path is None:
        return
    repeat = _CUE_REPEAT.get(name, 1)
    _play_async(path, repeat)


def play_completed() -> None:
    """Play the job-completed chime (Glass.aiff) asynchronously."""
    play_cue("completed")


def play_failed() -> None:
    """Play the job-failed sound (Basso.aiff) asynchronously."""
    play_cue("failed")


def play_stall() -> None:
    """Play the suspected-stall tap (Tink.aiff × 2) asynchronously."""
    play_cue("stall")
