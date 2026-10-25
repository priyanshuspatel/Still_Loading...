"""Tests for Chrome download detection, percentage calculation, UNO Q state code 9, and coexistence."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "mac-agent"))
sys.path.insert(0, str(ROOT / "uno-q"))

from app_lab_main import forward_once  # noqa: E402
from battery import BatteryReading, build_battery_message  # noqa: E402
from download_monitor import (  # noqa: E402
    CHROME_STATE_CANCELLED,
    CHROME_STATE_COMPLETE,
    CHROME_STATE_IN_PROGRESS,
    CHROME_STATE_INTERRUPTED,
    ChromeDownloadDetector,
    DownloadReporter,
    DownloadSnapshot,
    build_download_message,
    calculate_download_percent,
    unix_to_webkit_us,
)
from http_api import build_server  # noqa: E402
from matrix_display import (  # noqa: E402
    DOWNLOAD_COMPLETE_PERCENT_MS,
    render_completed_check_frame,
    render_percentage_frame,
    select_display_frame,
    validate_frame,
)
from messages import ProtocolError, validate_download_message  # noqa: E402
from sender import post_battery, post_display_mode, post_download, post_event  # noqa: E402
from state_engine import EngineConfig, StateEngine  # noqa: E402

TOKEN = "test-token-0123456789"


def _init_chrome_history_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE downloads (
                id INTEGER PRIMARY KEY,
                guid VARCHAR NOT NULL,
                current_path LONGVARCHAR NOT NULL,
                target_path LONGVARCHAR NOT NULL,
                start_time INTEGER NOT NULL,
                received_bytes INTEGER NOT NULL,
                total_bytes INTEGER NOT NULL,
                state INTEGER NOT NULL,
                danger_type INTEGER NOT NULL DEFAULT 0,
                interrupt_reason INTEGER NOT NULL DEFAULT 0,
                end_time INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _upsert_download_row(
    db_path: Path,
    *,
    row_id: int,
    guid: str,
    current_path: str,
    target_path: str,
    start_time: int,
    received_bytes: int,
    total_bytes: int,
    state: int,
    interrupt_reason: int = 0,
    end_time: int = 0,
) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO downloads (
                id, guid, current_path, target_path, start_time,
                received_bytes, total_bytes, state, interrupt_reason, end_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row_id,
                guid,
                current_path,
                target_path,
                start_time,
                received_bytes,
                total_bytes,
                state,
                interrupt_reason,
                end_time,
            ),
        )
        conn.commit()
    finally:
        conn.close()


class DownloadPercentageAndMatrixTests(unittest.TestCase):
    def test_percentage_calculations_across_required_milestones(self) -> None:
        total = 1_000_000_000  # 1 GB
        cases = [
            (0, total, False, (0, True)),
            (10_000_000, total, False, (1, True)),
            (430_000_000, total, False, (43, True)),
            (500_000_000, total, False, (50, True)),
            (860_000_000, total, False, (86, True)),
            (990_000_000, total, False, (99, True)),
            (total, total, True, (100, True)),
        ]
        for downloaded, tot, is_done, expected in cases:
            with self.subTest(downloaded=downloaded, expected=expected):
                self.assertEqual(
                    calculate_download_percent(downloaded, tot, is_completed=is_done),
                    expected,
                )

    def test_unknown_total_and_zero_byte_files_never_invent_percentage(self) -> None:
        self.assertEqual(calculate_download_percent(250_000, None, is_completed=False), (0, False))
        self.assertEqual(calculate_download_percent(250_000, 0, is_completed=False), (0, False))
        self.assertEqual(calculate_download_percent(0, 0, is_completed=False), (0, False))
        # Completed zero-byte download reports 100% cleanly without division by zero.
        self.assertEqual(calculate_download_percent(0, 0, is_completed=True), (100, True))

    def test_matrix_frames_for_download_milestones_and_unknown_total(self) -> None:
        for pct in (0, 1, 50, 86, 99):
            kind, frame = select_display_frame("download", progress=pct, elapsed_ms=100, progress_known=True)
            self.assertEqual(kind, "download_percent")
            validate_frame(frame)
            self.assertEqual(frame, render_percentage_frame(pct))

        # 100% shows 100 briefly, then transitions to completed check.
        k_100, f_100 = select_display_frame("download", progress=100, elapsed_ms=200, progress_known=True)
        self.assertEqual(k_100, "download_100")
        self.assertEqual(f_100, render_percentage_frame(100))

        k_chk, f_chk = select_display_frame(
            "download",
            progress=100,
            elapsed_ms=DOWNLOAD_COMPLETE_PERCENT_MS + 100,
            progress_known=True,
        )
        self.assertEqual(k_chk, "download_check")
        self.assertEqual(f_chk, render_completed_check_frame())

        # Unknown total never renders a fabricated 0% frame.
        k_unk, f_unk = select_display_frame("download", progress=0, elapsed_ms=200, progress_known=False)
        self.assertEqual(k_unk, "download_waiting")
        validate_frame(f_unk)
        self.assertNotEqual(f_unk, render_percentage_frame(0))


class ChromeDownloadDetectorLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.chrome_root = self.root / "Chrome"
        self.downloads_dir = self.root / "Downloads"
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.chrome_root / "Default" / "History"
        _init_chrome_history_db(self.db_path)

        self.mono = 100.0
        self.wall = 1_760_000_000.0

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _make_detector(self) -> ChromeDownloadDetector:
        return ChromeDownloadDetector(
            chrome_root=self.chrome_root,
            downloads_dir=self.downloads_dir,
            clock=lambda: self.mono,
            wall_clock=lambda: self.wall,
            missing_file_grace_s=0.5,
            enable_nsprogress=False,
        )

    def test_chrome_not_running_or_missing_dirs_returns_idle(self) -> None:
        detector = ChromeDownloadDetector(
            chrome_root=self.root / "NonExistentChrome",
            downloads_dir=self.root / "NonExistentDownloads",
            clock=lambda: self.mono,
            wall_clock=lambda: self.wall,
            enable_nsprogress=False,
        )
        snap = detector.poll()
        self.assertEqual(snap.state, "idle")
        self.assertFalse(snap.progress_known)

    def test_download_lifecycle_0_1_50_86_99_100_completed(self) -> None:
        # Pre-populate an old historical download before detector starts.
        _upsert_download_row(
            self.db_path,
            row_id=1,
            guid="old-guid-1",
            current_path=str(self.downloads_dir / "old.zip"),
            target_path=str(self.downloads_dir / "old.zip"),
            start_time=unix_to_webkit_us(self.wall - 3600),
            received_bytes=1000,
            total_bytes=1000,
            state=CHROME_STATE_COMPLETE,
        )

        detector = self._make_detector()
        self.assertEqual(detector.poll().state, "idle")

        # Start a new 1000-byte download in Chrome.
        self.mono += 1.0
        self.wall += 1.0
        cr_path = self.downloads_dir / "archive.tar.gz.crdownload"
        target_path = self.downloads_dir / "archive.tar.gz"
        cr_path.write_bytes(b"")
        start_us = unix_to_webkit_us(self.wall)

        _upsert_download_row(
            self.db_path,
            row_id=2,
            guid="dl-guid-2",
            current_path=str(cr_path),
            target_path=str(target_path),
            start_time=start_us,
            received_bytes=0,
            total_bytes=1000,
            state=CHROME_STATE_IN_PROGRESS,
        )

        # 0%
        snap = detector.poll()
        self.assertEqual(snap.state, "starting")
        self.assertEqual(snap.progress, 0)
        self.assertTrue(snap.progress_known)

        # 1%, 50%, 86%, 99% via real file growth on disk (even before SQLite updates received_bytes).
        for byte_count, expected_pct in ((10, 1), (500, 50), (860, 86), (990, 99)):
            self.mono += 0.25
            cr_path.write_bytes(b"x" * byte_count)
            snap = detector.poll()
            self.assertEqual(snap.state, "downloading")
            self.assertEqual(snap.progress, expected_pct)
            self.assertTrue(snap.progress_known)
            self.assertEqual(snap.downloaded_bytes, byte_count)
            self.assertEqual(snap.total_bytes, 1000)

        # Complete the download: rename .crdownload -> target_path and mark state=1 in DB.
        self.mono += 0.25
        cr_path.write_bytes(b"x" * 1000)
        cr_path.replace(target_path)
        _upsert_download_row(
            self.db_path,
            row_id=2,
            guid="dl-guid-2",
            current_path=str(target_path),
            target_path=str(target_path),
            start_time=start_us,
            received_bytes=1000,
            total_bytes=1000,
            state=CHROME_STATE_COMPLETE,
        )
        done = detector.poll()
        self.assertEqual(done.state, "completed")
        self.assertEqual(done.progress, 100)
        self.assertTrue(done.progress_known)

        # Subsequent poll returns to idle (does not replay completed forever).
        self.mono += 0.25
        self.assertEqual(detector.poll().state, "idle")

    def test_cancelled_download_and_disappearing_crdownload_never_show_fake_100(self) -> None:
        detector = self._make_detector()
        self.assertEqual(detector.poll().state, "idle")

        # Case 1: Chrome marks state=CANCELLED in History DB.
        self.mono += 1.0
        self.wall += 1.0
        cr1 = self.downloads_dir / "cancel1.iso.crdownload"
        tgt1 = self.downloads_dir / "cancel1.iso"
        cr1.write_bytes(b"a" * 420)
        start1 = unix_to_webkit_us(self.wall)
        _upsert_download_row(
            self.db_path,
            row_id=10,
            guid="guid-cancel-1",
            current_path=str(cr1),
            target_path=str(tgt1),
            start_time=start1,
            received_bytes=420,
            total_bytes=1000,
            state=CHROME_STATE_IN_PROGRESS,
        )
        s1 = detector.poll()
        self.assertEqual(s1.progress, 42)

        # User cancels in Chrome: .crdownload is deleted and DB sets state=2 (CANCELLED).
        self.mono += 0.25
        cr1.unlink()
        _upsert_download_row(
            self.db_path,
            row_id=10,
            guid="guid-cancel-1",
            current_path=str(cr1),
            target_path=str(tgt1),
            start_time=start1,
            received_bytes=420,
            total_bytes=1000,
            state=CHROME_STATE_CANCELLED,
        )
        c1 = detector.poll()
        self.assertEqual(c1.state, "cancelled")
        self.assertNotEqual(c1.progress, 100)

        # Case 2: .crdownload disappears before DB flushes state=2, and target file does NOT exist.
        self.mono += 1.0
        self.wall += 1.0
        cr2 = self.downloads_dir / "cancel2.iso.crdownload"
        tgt2 = self.downloads_dir / "cancel2.iso"
        cr2.write_bytes(b"b" * 670)
        start2 = unix_to_webkit_us(self.wall)
        _upsert_download_row(
            self.db_path,
            row_id=11,
            guid="guid-cancel-2",
            current_path=str(cr2),
            target_path=str(tgt2),
            start_time=start2,
            received_bytes=670,
            total_bytes=1000,
            state=CHROME_STATE_IN_PROGRESS,
        )
        self.assertEqual(detector.poll().progress, 67)

        # Delete .crdownload without creating tgt2 and while DB still says state=0.
        self.mono += 0.25
        cr2.unlink()
        _ = detector.poll()  # Begins grace timer
        self.mono += 0.60  # Past 0.5s grace window
        c2 = detector.poll()
        self.assertEqual(c2.state, "cancelled")
        self.assertNotEqual(c2.progress, 100)

    def test_failed_download_reports_failed_state(self) -> None:
        detector = self._make_detector()
        self.assertEqual(detector.poll().state, "idle")

        self.mono += 1.0
        self.wall += 1.0
        cr = self.downloads_dir / "broken.pkg.crdownload"
        tgt = self.downloads_dir / "broken.pkg"
        cr.write_bytes(b"z" * 350)
        start_us = unix_to_webkit_us(self.wall)
        _upsert_download_row(
            self.db_path,
            row_id=20,
            guid="guid-fail-20",
            current_path=str(cr),
            target_path=str(tgt),
            start_time=start_us,
            received_bytes=350,
            total_bytes=1000,
            state=CHROME_STATE_IN_PROGRESS,
        )
        self.assertEqual(detector.poll().progress, 35)

        self.mono += 0.25
        cr.unlink()
        _upsert_download_row(
            self.db_path,
            row_id=20,
            guid="guid-fail-20",
            current_path=str(cr),
            target_path=str(tgt),
            start_time=start_us,
            received_bytes=350,
            total_bytes=1000,
            state=CHROME_STATE_INTERRUPTED,
            interrupt_reason=20,
        )
        failed = detector.poll()
        self.assertEqual(failed.state, "failed")
        self.assertEqual(failed.progress, 35)
        self.assertNotEqual(failed.progress, 100)

    def test_multiple_concurrent_downloads_do_not_jump_randomly(self) -> None:
        detector = self._make_detector()
        self.assertEqual(detector.poll().state, "idle")

        self.mono += 1.0
        self.wall += 1.0
        cr_a = self.downloads_dir / "first.bin.crdownload"
        tgt_a = self.downloads_dir / "first.bin"
        cr_a.write_bytes(b"a" * 200)
        start_a = unix_to_webkit_us(self.wall)
        _upsert_download_row(
            self.db_path,
            row_id=30,
            guid="guid-first",
            current_path=str(cr_a),
            target_path=str(tgt_a),
            start_time=start_a,
            received_bytes=200,
            total_bytes=1000,
            state=CHROME_STATE_IN_PROGRESS,
        )
        self.assertEqual(detector.poll().progress, 20)

        # Start a second download 2 seconds later; focus switches to the newer download and stays there.
        self.mono += 2.0
        self.wall += 2.0
        cr_b = self.downloads_dir / "second.bin.crdownload"
        tgt_b = self.downloads_dir / "second.bin"
        cr_b.write_bytes(b"b" * 600)
        start_b = unix_to_webkit_us(self.wall)
        _upsert_download_row(
            self.db_path,
            row_id=31,
            guid="guid-second",
            current_path=str(cr_b),
            target_path=str(tgt_b),
            start_time=start_b,
            received_bytes=600,
            total_bytes=1000,
            state=CHROME_STATE_IN_PROGRESS,
        )

        # Even as first.bin continues growing, detector stays locked onto second.bin.
        for b_size, a_size, expected_pct in ((650, 300, 65), (720, 450, 72), (880, 900, 88)):
            self.mono += 0.25
            cr_a.write_bytes(b"a" * a_size)
            cr_b.write_bytes(b"b" * b_size)
            snap = detector.poll()
            self.assertEqual(snap.filename, "second.bin")
            self.assertEqual(snap.progress, expected_pct)


class DownloadDeduplicationAndCoexistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = StateEngine(
            EngineConfig(
                heartbeat_timeout_s=6,
                slow_progress_gap_s=6,
                download_complete_hold_s=4.0,
                download_failed_hold_s=3.0,
            )
        )
        self.httpd, self.job_log = build_server("127.0.0.1", 0, TOKEN, engine=self.engine)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def test_duplicate_percentages_are_not_sent_repeatedly(self) -> None:
        snapshots = [
            DownloadSnapshot("idle"),
            DownloadSnapshot("starting", "dl-1", "a.zip", 0, 1000, 0, True),
            DownloadSnapshot("downloading", "dl-1", "a.zip", 430, 1000, 43, True),
            DownloadSnapshot("downloading", "dl-1", "a.zip", 432, 1000, 43, True),
            DownloadSnapshot("downloading", "dl-1", "a.zip", 439, 1000, 43, True),
            DownloadSnapshot("downloading", "dl-1", "a.zip", 470, 1000, 47, True),
            DownloadSnapshot("completed", "dl-1", "a.zip", 1000, 1000, 100, True),
            DownloadSnapshot("idle"),
        ]
        sent: list[dict] = []

        def fake_send(msg: dict) -> dict:
            sent.append(msg)
            return {"delivered": True, "delivery": "accepted"}

        reporter = DownloadReporter(fake_send, read_fn=lambda: snapshots.pop(0))
        outcomes = [reporter.poll_once() for _ in range(len(snapshots))]

        self.assertEqual(outcomes[0]["status"], "idle")
        self.assertEqual(outcomes[1]["status"], "sent")       # 0%
        self.assertEqual(outcomes[2]["status"], "sent")       # 43%
        self.assertEqual(outcomes[3]["status"], "unchanged")  # 43% skipped
        self.assertEqual(outcomes[4]["status"], "unchanged")  # 43% skipped
        self.assertEqual(outcomes[5]["status"], "sent")       # 47%
        self.assertEqual(outcomes[6]["status"], "sent")       # 100% completed
        self.assertEqual(outcomes[7]["status"], "idle")       # idle suppressed during completion hold
        self.assertEqual([m["progress"] for m in sent], [0, 43, 47, 100])

    def test_end_to_end_download_to_uno_q_and_coexistence_with_battery(self) -> None:
        # 1. Configure auto mode with return_to_battery=True and an 82% battery reading.
        post_battery(
            self.base,
            TOKEN,
            build_battery_message(
                BatteryReading(82, "discharging"),
                display_mode="auto",
                return_to_battery=True,
            ),
        )
        self.assertEqual(self.engine.view.state, "battery")
        self.assertEqual(self.engine.view.code, 6)
        self.assertEqual(self.engine.view.progress, 82)

        # 2. Start a download in auto mode -> temporarily takes priority on the matrix (code 9).
        for pct in (42, 67, 86):
            msg = build_download_message(
                DownloadSnapshot("downloading", "dl-live", "ubuntu.iso", pct * 10, 1000, pct, True)
            )
            res = post_download(self.base, TOKEN, msg)
            self.assertTrue(res["delivered"])
            self.assertEqual(self.engine.view.state, "download")
            self.assertEqual(self.engine.view.code, 9)
            self.assertEqual(self.engine.view.progress, pct)

        # Verify App Lab forwarding sends (9, 86) to Bridge.call("set_job_lights", ...).
        calls: list[tuple[int, int]] = []
        status, pair = forward_once([self.base], TOKEN, lambda c, p: calls.append((c, p)), None)
        self.assertIn("forwarded download code=9 progress=86", status)
        self.assertEqual(calls[-1], (9, 86))

        # 3. Complete the download at t=50.0 -> shows 100% (code 9, progress 100) during hold window,
        #    then returns to battery 82% after hold expires.
        done_msg = build_download_message(
            DownloadSnapshot("completed", "dl-live", "ubuntu.iso", 1000, 1000, 100, True)
        )
        self.engine.apply_download(done_msg, now=50.0)
        self.assertEqual(self.engine.view.state, "download")
        self.assertEqual(self.engine.view.code, 9)
        self.assertEqual(self.engine.view.progress, 100)

        # Still holding at t=52.0s:
        self.assertEqual(self.engine.tick(52.0).state, "download")
        # Hold expires at t=54.1s -> automatically returns to battery 82%!
        settled = self.engine.tick(54.1)
        self.assertEqual(settled.state, "battery")
        self.assertEqual(settled.code, 6)
        self.assertEqual(settled.progress, 82)

        # 4. If user explicitly selects "battery" display mode, battery mode is preserved even during download.
        post_display_mode(self.base, TOKEN, "battery")
        post_download(
            self.base,
            TOKEN,
            build_download_message(
                DownloadSnapshot("downloading", "dl-2", "file.bin", 500, 1000, 50, True)
            ),
        )
        self.assertEqual(self.engine.view.state, "battery")
        self.assertEqual(self.engine.view.code, 6)
        self.assertEqual(self.engine.view.progress, 82)

    def test_download_validation_rejects_bad_messages(self) -> None:
        valid = build_download_message(
            DownloadSnapshot("downloading", "dl-1", "test.zip", 500, 1000, 50, True)
        )
        validate_download_message(valid)
        with self.assertRaises(ProtocolError):
            validate_download_message({**valid, "progress": 99, "progress_known": False})
        with self.assertRaises(ProtocolError):
            validate_download_message({**valid, "state": "completed", "progress": 99})
        with self.assertRaises(ProtocolError):
            validate_download_message({**valid, "extra_field": 123})


if __name__ == "__main__":
    unittest.main()
