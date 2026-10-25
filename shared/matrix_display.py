"""8x13 LED matrix frames and animation timeline for Still Loading...

The UNO Q matrix has 8 rows and 13 columns of blue LEDs with 3-bit grayscale
(brightness 0..7). Keep these bitmaps and timing constants in sync with
``uno-q/sketch/sketch.ino``.
"""

from __future__ import annotations

ROWS = 8
COLS = 13
MAX_BRIGHTNESS = 7

# Animation timing constants in milliseconds (mirrored in sketch.ino).
START_HEART_BLINKS = 2
START_HEART_PERIOD_MS = 650
START_HEART_ON_MS = 400
START_INTRO_MS = START_HEART_BLINKS * START_HEART_PERIOD_MS

RUNNING_CYCLE_MS = 8000
RUNNING_PERCENT_MS = 4400
RUNNING_WAIT_MS = 6600
DOT_STEP_MS = 450
SLOW_STEP_MS = 700

COMPLETE_HEART_BLINKS = 3
COMPLETE_HEART_PERIOD_MS = 750
COMPLETE_HEART_ON_MS = 450
COMPLETE_HEART_TOTAL_MS = COMPLETE_HEART_BLINKS * COMPLETE_HEART_PERIOD_MS
COMPLETE_PERCENT_MS = COMPLETE_HEART_TOTAL_MS + 1800
DOWNLOAD_COMPLETE_PERCENT_MS = 1800

# 3x5 pixel glyphs rendered on rows 1..5.
DIGIT_GLYPHS: dict[str, tuple[str, str, str, str, str]] = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "001", "001", "001"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
    "%": ("110", "001", "010", "100", "011"),
}

# 7x6 heart centered at columns 3..9, rows 1..6.
HEART_ROWS: tuple[str, ...] = (
    "0110110",
    "1111111",
    "1111111",
    "0111110",
    "0011100",
    "0001000",
)


def empty_frame() -> list[list[int]]:
    return [[0 for _ in range(COLS)] for _ in range(ROWS)]


def set_pixel(frame: list[list[int]], row: int, col: int, brightness: int) -> None:
    if 0 <= row < ROWS and 0 <= col < COLS:
        clamped = max(0, min(MAX_BRIGHTNESS, int(brightness)))
        frame[row][col] = clamped


def validate_frame(frame: list[list[int]]) -> bool:
    """Confirm the frame is 8x13 with 3-bit grayscale values 0..7."""
    if not isinstance(frame, list) or len(frame) != ROWS:
        raise ValueError(f"Frame must have {ROWS} rows")
    for row in frame:
        if not isinstance(row, list) or len(row) != COLS:
            raise ValueError(f"Each row must have {COLS} columns")
        for cell in row:
            if isinstance(cell, bool) or not isinstance(cell, int) or not 0 <= cell <= MAX_BRIGHTNESS:
                raise ValueError(f"Pixel brightness must be an integer 0..{MAX_BRIGHTNESS}")
    return True


def _draw_glyph(frame: list[list[int]], glyph: str, top_row: int, left_col: int, brightness: int) -> None:
    bitmap = DIGIT_GLYPHS[glyph]
    for r_idx, line in enumerate(bitmap):
        for c_idx, char in enumerate(line):
            if char == "1":
                set_pixel(frame, top_row + r_idx, left_col + c_idx, brightness)


def _draw_percent_symbol(frame: list[list[int]], top_row: int, left_col: int, brightness: int) -> None:
    """Draw the 4x5 '%' symbol mirrored in uno-q/sketch/sketch.ino."""
    # Upper dot
    set_pixel(frame, top_row, left_col, brightness)
    set_pixel(frame, top_row, left_col + 1, brightness)
    set_pixel(frame, top_row + 1, left_col, brightness)

    # Straight diagonal slash, from upper right to lower left
    set_pixel(frame, top_row, left_col + 3, brightness)
    set_pixel(frame, top_row + 1, left_col + 2, brightness)
    set_pixel(frame, top_row + 2, left_col + 1, brightness)
    set_pixel(frame, top_row + 3, left_col, brightness)

    # Lower dot
    set_pixel(frame, top_row + 3, left_col + 2, brightness)
    set_pixel(frame, top_row + 3, left_col + 3, brightness)
    set_pixel(frame, top_row + 4, left_col + 2, brightness)
    set_pixel(frame, top_row + 4, left_col + 3, brightness)


def render_heart_frame(brightness: int = 5, progress: int | None = None) -> list[list[int]]:
    """Calm centered heart. Optional progress bar on row 7."""
    frame = empty_frame()
    for r_idx, line in enumerate(HEART_ROWS):
        for c_idx, char in enumerate(line):
            if char == "1":
                set_pixel(frame, 1 + r_idx, 3 + c_idx, brightness)
    if progress is not None and progress > 0:
        _draw_bar(frame, row=7, progress=progress, brightness=3)
    return frame


def render_waiting_dots_frame(
    active_dot: int = 0,
    progress: int | None = None,
    slow: bool = False,
) -> list[list[int]]:
    """Three waiting dots ('...') at columns 3, 6, 9."""
    frame = empty_frame()
    cols = (3, 6, 9)
    active = active_dot % 3
    for idx, col in enumerate(cols):
        level = 5 if idx == active else 2
        set_pixel(frame, 3, col, level)
        if slow:
            set_pixel(frame, 4, col, 3 if idx == active else 1)
    if slow:
        # Gentle slow-cue guide ticks at the bottom corners.
        set_pixel(frame, 6, 1, 3)
        set_pixel(frame, 6, 11, 3)
    if progress is not None and progress > 0:
        _draw_bar(frame, row=7, progress=progress, brightness=4)
    return frame


def _draw_bar(frame: list[list[int]], row: int, progress: int, brightness: int = 4) -> None:
    clamped = max(0, min(100, int(progress)))
    if clamped <= 0:
        return
    lit = max(1, (clamped * COLS) // 100)
    for col in range(lit):
        set_pixel(frame, row, col, brightness)


def render_percentage_frame(
    percent: int,
    *,
    charging: bool = False,
    slow: bool = False,
    pulse_step: int = 0,
) -> list[list[int]]:
    """Render 0%..99% with a '%' sign, or '100' with a full row-7 cue.

     On an 8x13 matrix, three digits plus '%' would require 15 columns.
     '100' uses three 3x5 digits across columns 1..11 plus a full 13-pixel
     completion/charged bar on row 7.
    """
    if isinstance(percent, bool) or not isinstance(percent, int) or not 0 <= percent <= 100:
        raise ValueError("percent must be an integer from 0 to 100")

    frame = empty_frame()
    if percent == 100:
        _draw_glyph(frame, "1", top_row=1, left_col=1, brightness=6)
        _draw_glyph(frame, "0", top_row=1, left_col=5, brightness=6)
        _draw_glyph(frame, "0", top_row=1, left_col=9, brightness=6)
    elif percent < 10:
        _draw_glyph(frame, str(percent), top_row=1, left_col=3, brightness=6)
        _draw_percent_symbol(frame, top_row=1, left_col=8, brightness=4)
    else:
        _draw_glyph(frame, str(percent // 10), top_row=1, left_col=1, brightness=6)
        _draw_glyph(frame, str(percent % 10), top_row=1, left_col=5, brightness=6)
        _draw_percent_symbol(frame, top_row=1, left_col=9, brightness=4)

    if percent == 100:
        for c in range(COLS):
            set_pixel(frame, 7, c, 5)
    elif charging:
        _draw_bar(frame, row=7, progress=percent, brightness=3)
        head = (pulse_step % COLS)
        set_pixel(frame, 7, head, 6)
    elif slow:
        _draw_bar(frame, row=7, progress=percent, brightness=3)
        set_pixel(frame, 6, 0, 3)
        set_pixel(frame, 6, COLS - 1, 3)
    elif percent > 0:
        _draw_bar(frame, row=7, progress=percent, brightness=3)

    return frame


def render_stall_frame(blink_on: bool = True, progress: int | None = None) -> list[list[int]]:
    """Distinct suspected-stall warning: framed exclamation, never an X."""
    frame = empty_frame()
    level = 6 if blink_on else 3
    for row in (1, 2, 3, 4):
        set_pixel(frame, row, 6, level)
    set_pixel(frame, 6, 6, level)
    # Side warning brackets distinguish suspected_stall from waiting dots and X.
    for row in (2, 3, 4, 5):
        set_pixel(frame, row, 2, 3 if blink_on else 1)
        set_pixel(frame, row, 10, 3 if blink_on else 1)
    if progress is not None and progress > 0:
        _draw_bar(frame, row=7, progress=progress, brightness=2)
    return frame


def render_failed_frame() -> list[list[int]]:
    """Steady X symbol with corner markers. Distinct from heart, dots, and check."""
    frame = empty_frame()
    for i in range(5):
        set_pixel(frame, 1 + i, 4 + i, 7)
        set_pixel(frame, 1 + i, 8 - i, 7)
    set_pixel(frame, 1, 1, 4)
    set_pixel(frame, 5, 1, 4)
    set_pixel(frame, 1, 11, 4)
    set_pixel(frame, 5, 11, 4)
    return frame


def render_completed_check_frame() -> list[list[int]]:
    """Calm settled checkmark for completed jobs."""
    frame = empty_frame()
    points = ((4, 3), (5, 4), (4, 5), (3, 6), (2, 7), (1, 8))
    for row, col in points:
        set_pixel(frame, row, col, 5)
    for col in range(3, 10):
        set_pixel(frame, 7, col, 2)
    return frame


def render_unavailable_frame() -> list[list[int]]:
    """Neutral '--' indicator when battery mode has no reading yet."""
    frame = empty_frame()
    for col in (3, 4, 5, 7, 8, 9):
        set_pixel(frame, 3, col, 3)
    return frame


def select_display_frame(
    state: str,
    progress: int = 0,
    elapsed_ms: int = 0,
    *,
    progress_known: bool | None = None,
) -> tuple[str, list[list[int]]]:
    """Return ``(frame_kind, frame)`` for a state at ``elapsed_ms`` since entering it.

    When ``progress_known`` is False (or omitted and ``progress <= 0`` for a
    job state), running and slow states never display a fabricated percentage.
    """
    if progress_known is None:
        known = progress > 0 or state in {"completed", "battery", "battery_charging", "download"}
    else:
        known = bool(progress_known)

    ms = max(0, int(elapsed_ms))

    if state == "idle":
        dot = (ms // DOT_STEP_MS) % 3
        return ("idle_dots", render_waiting_dots_frame(dot, progress=None))

    if state == "running":
        if ms < START_INTRO_MS:
            within = ms % START_HEART_PERIOD_MS
            bright = 5 if within < START_HEART_ON_MS else 1
            return (
                "start_heart",
                render_heart_frame(bright, progress if known else None),
            )
        cycle = (ms - START_INTRO_MS) % RUNNING_CYCLE_MS
        if known and 0 <= progress <= 100:
            if cycle < RUNNING_PERCENT_MS:
                return ("percentage", render_percentage_frame(progress))
            if cycle < RUNNING_WAIT_MS:
                dot = (ms // DOT_STEP_MS) % 3
                return ("waiting_dots", render_waiting_dots_frame(dot, progress=progress))
            return ("heartbeat", render_heart_frame(4, progress=progress))
        if cycle < RUNNING_WAIT_MS:
            dot = (ms // DOT_STEP_MS) % 3
            return ("waiting_dots", render_waiting_dots_frame(dot, progress=None))
        return ("heartbeat", render_heart_frame(4, progress=None))

    if state == "slow":
        cycle = ms % RUNNING_CYCLE_MS
        if known and 0 <= progress <= 100 and cycle < RUNNING_PERCENT_MS:
            return ("slow_percentage", render_percentage_frame(progress, slow=True))
        dot = (ms // SLOW_STEP_MS) % 3
        return (
            "slow_waiting",
            render_waiting_dots_frame(dot, progress=progress if known else None, slow=True),
        )

    if state == "suspected_stall":
        blink_on = ((ms // 400) % 2) == 0
        return (
            "suspected_stall",
            render_stall_frame(blink_on=blink_on, progress=progress if known else None),
        )

    if state == "failed":
        return ("failed_x", render_failed_frame())

    if state == "completed":
        if ms < COMPLETE_HEART_TOTAL_MS:
            within = ms % COMPLETE_HEART_PERIOD_MS
            bright = 5 if within < COMPLETE_HEART_ON_MS else 1
            return ("completed_heart", render_heart_frame(bright, progress=100))
        if ms < COMPLETE_PERCENT_MS:
            return ("completed_100", render_percentage_frame(100))
        return ("completed_check", render_completed_check_frame())

    if state == "battery":
        return ("battery_percent", render_percentage_frame(progress))

    if state == "battery_charging":
        step = ms // 250
        return (
            "battery_charging",
            render_percentage_frame(progress, charging=True, pulse_step=step),
        )

    if state == "battery_unavailable":
        return ("battery_unavailable", render_unavailable_frame())

    if state == "download":
        if not known:
            dot = (ms // DOT_STEP_MS) % 3
            return ("download_waiting", render_waiting_dots_frame(dot, progress=None))
        if progress >= 100:
            if ms < DOWNLOAD_COMPLETE_PERCENT_MS:
                return ("download_100", render_percentage_frame(100))
            return ("download_check", render_completed_check_frame())
        return ("download_percent", render_percentage_frame(progress))

    raise ValueError(f"Unknown display state: {state!r}")
