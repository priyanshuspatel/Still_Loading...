"""Monitor Google Chrome downloads on macOS and send real progress to the UNO Q.

Architecture:
1. Primary metadata source: Chrome's local SQLite ``History`` database
   (``~/Library/Application Support/Google/Chrome/<Profile>/History``), querying
   the ``downloads`` table via a safe temporary copy (including ``History-wal``,
   ``History-shm``, and ``History-journal``) so Chrome is never locked or slowed.
2. Real-time byte source: ``os.stat()`` on the active ``current_path`` /
   ``.crdownload`` file on disk, combined with ``received_bytes`` and
   ``total_bytes`` from Chrome's ``downloads`` table.
3. Completion verification: Never assumes a download reached 100% merely because
   a ``.crdownload`` file disappeared. A download is marked ``completed`` (100%)
   only when Chrome's ``downloads.state == 1`` (COMPLETE) or when the final
   target file exists on disk with ``size >= total_bytes > 0``. If a
   ``.crdownload`` file disappears without completion, it is marked ``cancelled``.
4. Multiple-download policy: Sticky Most-Recently-Started Active Download.
   When multiple downloads are active concurrently, the monitor locks onto the
   most recently started active download and stays with it until it finishes
   (or a newer download is started), preventing the display from jumping
   randomly between files.

Examples:
    python3 mac-agent/download_monitor.py --once --dry-run
    python3 mac-agent/download_monitor.py --config mac-agent/config.local.json
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

MAC_AGENT = Path(__file__).resolve().parent
ROOT = MAC_AGENT.parent
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(MAC_AGENT))

from messages import ProtocolError, validate_download_message  # noqa: E402
from send_events import resolve_target  # noqa: E402
from sender import post_download  # noqa: E402
from simulator import format_timestamp  # noqa: E402

# Chrome DownloadItem::DownloadState values in the SQLite `downloads` table.
CHROME_STATE_IN_PROGRESS = 0
CHROME_STATE_COMPLETE = 1
CHROME_STATE_CANCELLED = 2
CHROME_STATE_INTERRUPTED = 3

# Chromium timestamps count microseconds since 1601-01-01 00:00:00 UTC.
_WEBKIT_EPOCH_OFFSET_US = 11_644_473_600 * 1_000_000

# Grace window (seconds) when a .crdownload file vanishes before declaring cancellation,
# allowing Chrome to finish renaming .crdownload -> target_path or flushing SQLite.
_MISSING_FILE_GRACE_S = 0.75


@dataclass(frozen=True)
class ChromeDownloadRow:
    """One row from Chrome's SQLite ``downloads`` table."""

    profile: str
    row_id: int
    guid: str
    current_path: str
    target_path: str
    start_time_us: int
    received_bytes: int
    total_bytes: int
    state: int
    interrupt_reason: int
    end_time_us: int


@dataclass(frozen=True)
class DownloadSnapshot:
    """Normalized state of the currently focused download (or idle when none)."""

    state: str  # "idle", "starting", "downloading", "completed", "failed", "cancelled"
    download_id: str | None = None
    filename: str | None = None
    downloaded_bytes: int = 0
    total_bytes: int | None = None
    progress: int = 0
    progress_known: bool = False


@dataclass
class _TrackedDownload:
    download_id: str
    target_key: str
    filename: str
    current_path: str
    target_path: str
    start_order: int
    downloaded_bytes: int
    total_bytes: int | None
    first_seen_at: float
    last_active_at: float
    missing_since: float | None = None


def unix_to_webkit_us(unix_seconds: float) -> int:
    """Convert Unix epoch seconds to Chromium/WebKit timestamp microseconds."""
    return int(unix_seconds * 1_000_000) + _WEBKIT_EPOCH_OFFSET_US


def calculate_download_percent(
    downloaded_bytes: int,
    total_bytes: int | None,
    *,
    is_completed: bool = False,
) -> tuple[int, bool]:
    """Calculate ``(percent, progress_known)`` from real byte counts.

    - Returns ``(100, True)`` when ``is_completed`` is True.
    - Returns ``(0, False)`` when ``total_bytes`` is None or ``<= 0`` (unknown total size).
    - Never fabricates a percentage when total size is unknown.
    """
    if is_completed:
        return 100, True
    if total_bytes is None or isinstance(total_bytes, bool) or total_bytes <= 0:
        return 0, False
    if isinstance(downloaded_bytes, bool) or downloaded_bytes <= 0:
        return 0, True
    if downloaded_bytes >= total_bytes:
        return 100, True
    pct = (int(downloaded_bytes) * 100) // int(total_bytes)
    return max(0, min(100, pct)), True


def default_chrome_root() -> Path:
    return Path.home() / "Library" / "Application Support" / "Google" / "Chrome"


def default_downloads_dir() -> Path:
    return Path.home() / "Downloads"


def discover_chrome_history_dbs(chrome_root: Path | None = None) -> list[tuple[str, Path]]:
    """Find ``(profile_name, History_path)`` pairs under Chrome's user data directory."""
    root = chrome_root if chrome_root is not None else default_chrome_root()
    try:
        if not root.exists() or not root.is_dir():
            return []
    except OSError:
        return []

    candidates: list[tuple[float, str, Path]] = []
    try:
        # Check whether root itself is a profile directory containing History.
        direct_history = root / "History"
        if direct_history.is_file():
            mtime = _latest_sqlite_mtime(direct_history)
            return [(root.name or "Default", direct_history)]

        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            name = entry.name
            if name != "Default" and not name.startswith("Profile "):
                continue
            hist = entry / "History"
            if hist.is_file():
                candidates.append((_latest_sqlite_mtime(hist), name, hist))
    except OSError:
        return []

    candidates.sort(key=lambda item: item[0], reverse=True)
    return [(name, path) for _mtime, name, path in candidates]


def _latest_sqlite_mtime(db_path: Path) -> float:
    """Return the latest mtime across History, History-wal, and History-journal."""
    latest = 0.0
    for suffix in ("", "-wal", "-journal", "-shm"):
        candidate = db_path.parent / (db_path.name + suffix)
        try:
            st = candidate.stat()
            if st.st_mtime > latest:
                latest = st.st_mtime
        except OSError:
            continue
    return latest


def read_chrome_downloads_from_db(
    db_path: Path,
    profile: str = "Default",
    limit: int = 25,
) -> list[ChromeDownloadRow]:
    """Safely copy a Chrome History SQLite DB (plus WAL/journal) and read recent downloads."""
    try:
        if not db_path.is_file():
            return []
    except OSError:
        return []

    query = (
        "SELECT id, guid, current_path, target_path, start_time, "
        "received_bytes, total_bytes, state, interrupt_reason, end_time "
        "FROM downloads ORDER BY start_time DESC, id DESC LIMIT ?"
    )

    try:
        with tempfile.TemporaryDirectory(prefix="still-loading-chrome-") as tmp_dir:
            tmp_root = Path(tmp_dir)
            tmp_db = tmp_root / "History"
            shutil.copyfile(db_path, tmp_db)
            for suffix in ("-wal", "-shm", "-journal"):
                sidecar = db_path.parent / (db_path.name + suffix)
                try:
                    if sidecar.is_file():
                        shutil.copyfile(sidecar, tmp_root / ("History" + suffix))
                except OSError:
                    continue

            raw_rows = _query_sqlite_rows(tmp_db, query, (limit,))
    except (OSError, sqlite3.Error):
        return []

    rows: list[ChromeDownloadRow] = []
    for raw in raw_rows:
        try:
            rows.append(
                ChromeDownloadRow(
                    profile=profile,
                    row_id=int(raw[0]),
                    guid=str(raw[1] or ""),
                    current_path=str(raw[2] or ""),
                    target_path=str(raw[3] or ""),
                    start_time_us=int(raw[4] or 0),
                    received_bytes=max(0, int(raw[5] or 0)),
                    total_bytes=max(0, int(raw[6] or 0)),
                    state=int(raw[7] if raw[7] is not None else -1),
                    interrupt_reason=int(raw[8] or 0),
                    end_time_us=int(raw[9] or 0),
                )
            )
        except (ValueError, TypeError, IndexError):
            continue
    return rows


def _query_sqlite_rows(tmp_db: Path, query: str, params: tuple) -> list[tuple]:
    """Query the temporary SQLite copy, falling back to immutable mode if needed."""
    try:
        conn = sqlite3.connect(str(tmp_db), timeout=0.5)
        try:
            return list(conn.execute(query, params).fetchall())
        finally:
            conn.close()
    except sqlite3.Error:
        uri = f"{tmp_db.resolve().as_uri()}?immutable=1"
        conn = sqlite3.connect(uri, uri=True, timeout=0.5)
        try:
            return list(conn.execute(query, params).fetchall())
        finally:
            conn.close()


def _safe_file_size(path_str: str | Path | None) -> int | None:
    if not path_str:
        return None
    try:
        st = Path(path_str).stat()
    except OSError:
        return None
    return max(0, int(st.st_size))


def _target_key(target_path: str, current_path: str) -> str:
    """Stable key linking a .crdownload file and its Chrome History row."""
    if target_path:
        return os.path.normpath(target_path)
    if current_path.endswith(".crdownload"):
        return os.path.normpath(current_path[: -len(".crdownload")])
    return os.path.normpath(current_path)


def _display_filename(target_path: str, current_path: str) -> str:
    base = Path(target_path).name if target_path else ""
    if not base and current_path:
        name = Path(current_path).name
        base = name[: -len(".crdownload")] if name.endswith(".crdownload") else name
    return base or "download"


def _is_unconfirmed_temp(path_str: str) -> bool:
    name = Path(path_str).name
    return name.startswith("Unconfirmed ") and (
        name.endswith(".crdownload") or name[len("Unconfirmed ") :].isdigit()
    )


class MacOSProgressSubscriber:
    """Optional macOS Foundation NSProgress subscriber for ~/Downloads.

    Chrome's ``DownloadStatusUpdaterMac`` (``CrNSProgressUserData``) publishes
    an ``NSProgress`` for every active download with ``totalUnitCount`` =
    ``total_bytes`` and ``completedUnitCount`` = ``received_bytes`` immediately,
    even before Chrome's 10-second SQLite ``HistoryBackend`` commit timer flushes
    the new row to disk.
    """

    def __init__(self, downloads_dir: Path) -> None:
        self._downloads_dir = downloads_dir
        self._available = False
        self._progress_ptrs: set[int] = set()
        self._keepalive: list[object] = []
        self._init_objc()

    def _init_objc(self) -> None:
        if sys.platform != "darwin":
            return
        try:
            import ctypes

            objc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.A.dylib")
            ctypes.cdll.LoadLibrary("/System/Library/Frameworks/Foundation.framework/Foundation")
            libsystem = ctypes.cdll.LoadLibrary("/usr/lib/libSystem.B.dylib")

            objc.objc_getClass.restype = ctypes.c_void_p
            objc.objc_getClass.argtypes = [ctypes.c_char_p]
            objc.sel_registerName.restype = ctypes.c_void_p
            objc.sel_registerName.argtypes = [ctypes.c_char_p]
            objc.objc_retain.restype = ctypes.c_void_p
            objc.objc_retain.argtypes = [ctypes.c_void_p]

            self._objc = objc
            self._ctypes = ctypes
            self._msg_ptr = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(
                ("objc_msgSend", objc)
            )
            self._msg_ptr_ptr = ctypes.CFUNCTYPE(
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
            )(("objc_msgSend", objc))
            self._msg_ptr_ptr_ptr = ctypes.CFUNCTYPE(
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_void_p,
            )(("objc_msgSend", objc))
            self._msg_str = ctypes.CFUNCTYPE(
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p
            )(("objc_msgSend", objc))
            self._msg_cstr = ctypes.CFUNCTYPE(
                ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p
            )(("objc_msgSend", objc))
            self._msg_i64 = ctypes.CFUNCTYPE(
                ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p
            )(("objc_msgSend", objc))
            self._msg_void_ptr = ctypes.CFUNCTYPE(
                None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
            )(("objc_msgSend", objc))
            self._msg_date = ctypes.CFUNCTYPE(
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_double
            )(("objc_msgSend", objc))

            class BlockDescriptor(ctypes.Structure):
                _fields_ = [
                    ("reserved", ctypes.c_ulong),
                    ("size", ctypes.c_ulong),
                    ("signature", ctypes.c_char_p),
                ]

            class BlockLiteral(ctypes.Structure):
                _fields_ = [
                    ("isa", ctypes.c_void_p),
                    ("flags", ctypes.c_int),
                    ("reserved", ctypes.c_int),
                    ("invoke", ctypes.c_void_p),
                    ("descriptor", ctypes.POINTER(BlockDescriptor)),
                ]

            global_block_sym = ctypes.c_void_p.in_dll(libsystem, "_NSConcreteGlobalBlock")
            desc = BlockDescriptor(0, ctypes.sizeof(BlockLiteral), b'@?@"NSProgress"')
            pub_func_type = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)

            def _on_publish(_block_ptr: int, progress_ptr: int) -> int | None:
                if progress_ptr:
                    objc.objc_retain(progress_ptr)
                    self._progress_ptrs.add(int(progress_ptr))
                return None

            pub_cb = pub_func_type(_on_publish)
            pub_block = BlockLiteral(
                ctypes.addressof(global_block_sym),
                (1 << 28) | (1 << 30),
                0,
                ctypes.cast(pub_cb, ctypes.c_void_p).value,
                ctypes.pointer(desc),
            )

            ns_str = self._msg_str(
                objc.objc_getClass(b"NSString"),
                objc.sel_registerName(b"stringWithUTF8String:"),
                str(self._downloads_dir).encode("utf-8"),
            )
            ns_url = self._msg_ptr_ptr(
                objc.objc_getClass(b"NSURL"),
                objc.sel_registerName(b"fileURLWithPath:"),
                ns_str,
            )
            sub = self._msg_ptr_ptr_ptr(
                objc.objc_getClass(b"NSProgress"),
                objc.sel_registerName(b"addSubscriberForFileURL:withPublishingHandler:"),
                ns_url,
                ctypes.cast(ctypes.pointer(pub_block), ctypes.c_void_p),
            )
            self._keepalive.extend([desc, pub_cb, pub_block, sub])
            self._available = bool(sub)
        except Exception:  # noqa: BLE001 - optional macOS enhancement must never crash
            self._available = False

    def snapshot(self) -> dict[str, tuple[int, int | None]]:
        """Return ``{norm_path: (completed_bytes, total_bytes)}`` from live NSProgress."""
        if not self._available:
            return {}
        result: dict[str, tuple[int, int | None]] = {}
        try:
            objc = self._objc
            runloop = self._msg_ptr(
                objc.objc_getClass(b"NSRunLoop"),
                objc.sel_registerName(b"currentRunLoop"),
            )
            dt = self._msg_date(
                objc.objc_getClass(b"NSDate"),
                objc.sel_registerName(b"dateWithTimeIntervalSinceNow:"),
                0.005,
            )
            self._msg_void_ptr(runloop, objc.sel_registerName(b"runUntilDate:"), dt)

            sel_file_url = objc.sel_registerName(b"fileURL")
            sel_user_info = objc.sel_registerName(b"userInfo")
            sel_obj_for_key = objc.sel_registerName(b"objectForKey:")
            sel_path = objc.sel_registerName(b"path")
            sel_utf8 = objc.sel_registerName(b"UTF8String")
            sel_total = objc.sel_registerName(b"totalUnitCount")
            sel_completed = objc.sel_registerName(b"completedUnitCount")
            key_file_url = self._msg_str(
                objc.objc_getClass(b"NSString"),
                objc.sel_registerName(b"stringWithUTF8String:"),
                b"NSProgressFileURLKey",
            )

            for ptr in list(self._progress_ptrs):
                url_ptr = self._msg_ptr(ptr, sel_file_url)
                if not url_ptr:
                    uinfo = self._msg_ptr(ptr, sel_user_info)
                    if uinfo:
                        url_ptr = self._msg_ptr_ptr(uinfo, sel_obj_for_key, key_file_url)
                if not url_ptr:
                    continue
                path_ns = self._msg_ptr(url_ptr, sel_path)
                if not path_ns:
                    continue
                raw_path = self._msg_cstr(path_ns, sel_utf8)
                if not raw_path:
                    continue
                norm = os.path.normpath(raw_path.decode("utf-8", errors="ignore"))
                total = int(self._msg_i64(ptr, sel_total))
                completed = max(0, int(self._msg_i64(ptr, sel_completed)))
                result[norm] = (completed, total if total > 0 else None)
        except Exception:  # noqa: BLE001
            return result
        return result


class ChromeDownloadDetector:
    """Stateful detector that tracks Chrome downloads across polls.

    Policy for concurrent downloads:
    - Focuses on the most recently started active download (`start_order`).
    - Remains locked onto that download while it is active unless an even newer
      download starts, avoiding random jumping between concurrent files.
    """

    def __init__(
        self,
        *,
        chrome_root: Path | None = None,
        downloads_dir: Path | None = None,
        clock=time.monotonic,
        wall_clock=time.time,
        missing_file_grace_s: float = _MISSING_FILE_GRACE_S,
        enable_nsprogress: bool | None = None,
    ) -> None:
        self.chrome_root = chrome_root if chrome_root is not None else default_chrome_root()
        self.downloads_dir = downloads_dir if downloads_dir is not None else default_downloads_dir()
        self._clock = clock
        self._wall_clock = wall_clock
        self._missing_file_grace_s = missing_file_grace_s
        use_ns = (downloads_dir is None) if enable_nsprogress is None else bool(enable_nsprogress)
        self._nsprogress = MacOSProgressSubscriber(self.downloads_dir) if use_ns else None

        self._started_mono = float(self._clock())
        self._started_wall = float(self._wall_clock())
        self._started_webkit_us = unix_to_webkit_us(self._started_wall)

        self._active: dict[str, _TrackedDownload] = {}
        self._focused_key: str | None = None
        self._finished_keys: set[str] = set()
        self._baseline_done = False
        self._baseline_row_keys: set[tuple[str, int]] = set()
        self._synthetic_seq = 0

    def poll(self) -> DownloadSnapshot:
        """Inspect Chrome History DBs and Downloads folder and return current snapshot."""
        now_mono = float(self._clock())
        now_wall = float(self._wall_clock())

        db_rows = self._read_all_db_rows()
        crdownload_files = self._scan_crdownload_files(now_wall)
        nsprogress_map = self._nsprogress.snapshot() if self._nsprogress is not None else {}

        if not self._baseline_done:
            self._initialize_baseline(db_rows, crdownload_files)
            self._baseline_done = True

        return self._evaluate(db_rows, crdownload_files, nsprogress_map, now_mono)

    def _read_all_db_rows(self) -> list[ChromeDownloadRow]:
        rows: list[ChromeDownloadRow] = []
        for profile, db_path in discover_chrome_history_dbs(self.chrome_root):
            rows.extend(read_chrome_downloads_from_db(db_path, profile=profile))
        rows.sort(key=lambda r: (r.start_time_us, r.row_id), reverse=True)
        return rows

    def _scan_crdownload_files(self, now_wall: float) -> dict[str, tuple[Path, int, float]]:
        """Return ``{norm_crdownload_path: (Path, size_bytes, mtime)}``."""
        found: dict[str, tuple[Path, int, float]] = {}
        try:
            if not self.downloads_dir.exists() or not self.downloads_dir.is_dir():
                return found
            for entry in self.downloads_dir.iterdir():
                if not entry.name.endswith(".crdownload"):
                    continue
                try:
                    st = entry.stat()
                except OSError:
                    continue
                # Ignore stale leftover .crdownload files from long before startup
                # unless they were modified recently (within 60s of startup or later).
                if st.st_mtime < self._started_wall - 60.0:
                    continue
                found[os.path.normpath(str(entry))] = (entry, max(0, int(st.st_size)), float(st.st_mtime))
        except OSError:
            return found
        return found

    def _initialize_baseline(
        self,
        db_rows: list[ChromeDownloadRow],
        crdownload_files: dict[str, tuple[Path, int, float]],
    ) -> None:
        """Record pre-existing completed/failed/stale DB rows so history is not replayed."""
        for row in db_rows:
            row_id_pair = (row.profile, row.row_id)
            if row.state != CHROME_STATE_IN_PROGRESS:
                self._baseline_row_keys.add(row_id_pair)
                continue
            # If a DB row claims IN_PROGRESS at startup, only treat it as live if its
            # .crdownload or active current_path is actually present in crdownload_files.
            cur_norm = os.path.normpath(row.current_path) if row.current_path else ""
            tgt_cr = os.path.normpath(row.target_path + ".crdownload") if row.target_path else ""
            if cur_norm not in crdownload_files and tgt_cr not in crdownload_files:
                self._baseline_row_keys.add(row_id_pair)

    def _evaluate(
        self,
        db_rows: list[ChromeDownloadRow],
        crdownload_files: dict[str, tuple[Path, int, float]],
        nsprogress_map: dict[str, tuple[int, int | None]],
        now_mono: float,
    ) -> DownloadSnapshot:
        matched_crdownloads: set[str] = set()
        terminal_candidates: list[tuple[int, DownloadSnapshot]] = []

        # 1. Process Chrome History DB rows.
        for row in db_rows:
            row_id_pair = (row.profile, row.row_id)
            tkey = _target_key(row.target_path, row.current_path)
            if not tkey:
                tkey = f"{row.profile}:{row.row_id}"

            if row_id_pair in self._baseline_row_keys and tkey not in self._active:
                continue

            dl_id = row.guid[:32] if row.guid else f"chrome-{row.profile}-{row.row_id}"
            dl_id = "".join(ch if (ch.isalnum() or ch in "-_") else "-" for ch in dl_id) or f"dl-{row.row_id}"
            filename = _display_filename(row.target_path, row.current_path)

            cur_norm = os.path.normpath(row.current_path) if row.current_path else ""
            tgt_cr_norm = os.path.normpath(row.target_path + ".crdownload") if row.target_path else ""
            cr_info = crdownload_files.get(cur_norm) or crdownload_files.get(tgt_cr_norm)
            if cur_norm in crdownload_files:
                matched_crdownloads.add(cur_norm)
            if tgt_cr_norm in crdownload_files:
                matched_crdownloads.add(tgt_cr_norm)

            if row.state == CHROME_STATE_IN_PROGRESS:
                if tkey in self._finished_keys:
                    continue

                disk_cr_bytes = cr_info[1] if cr_info is not None else _safe_file_size(row.current_path)
                # Note: When Chrome finishes a download, current_path is updated to target_path,
                # or target_path appears on disk before state=1 is flushed to SQLite.
                target_bytes = _safe_file_size(row.target_path) if row.target_path else None
                total_bytes = row.total_bytes if row.total_bytes > 0 else None

                # Check if the .crdownload is gone and the final target_path is already complete on disk.
                cr_exists = (
                    cr_info is not None
                    or (row.current_path.endswith(".crdownload") and disk_cr_bytes is not None)
                )
                if (
                    not cr_exists
                    and target_bytes is not None
                    and total_bytes is not None
                    and target_bytes >= total_bytes
                ):
                    self._active.pop(tkey, None)
                    self._finished_keys.add(tkey)
                    self._baseline_row_keys.add(row_id_pair)
                    terminal_candidates.append(
                        (
                            row.start_time_us,
                            DownloadSnapshot(
                                state="completed",
                                download_id=dl_id,
                                filename=filename,
                                downloaded_bytes=total_bytes,
                                total_bytes=total_bytes,
                                progress=100,
                                progress_known=True,
                            ),
                        )
                    )
                    continue

                tracked = self._active.get(tkey)
                if not cr_exists and tracked is not None:
                    # The .crdownload file vanished while DB still says state=0.
                    # Wait briefly for Chrome to either rename target_path or flush state=1/2/3.
                    if tracked.missing_since is None:
                        tracked.missing_since = now_mono
                    elif now_mono - tracked.missing_since >= self._missing_file_grace_s:
                        self._active.pop(tkey, None)
                        self._finished_keys.add(tkey)
                        self._baseline_row_keys.add(row_id_pair)
                        terminal_candidates.append(
                            (
                                tracked.start_order,
                                DownloadSnapshot(
                                    state="cancelled",
                                    download_id=tracked.download_id,
                                    filename=tracked.filename,
                                    downloaded_bytes=tracked.downloaded_bytes,
                                    total_bytes=tracked.total_bytes,
                                    progress=0,
                                    progress_known=False,
                                ),
                            )
                        )
                    continue

                live_bytes = row.received_bytes
                if disk_cr_bytes is not None and disk_cr_bytes > live_bytes:
                    live_bytes = disk_cr_bytes
                if tracked is not None and live_bytes < tracked.downloaded_bytes:
                    live_bytes = tracked.downloaded_bytes

                if tracked is None:
                    tracked = _TrackedDownload(
                        download_id=dl_id,
                        target_key=tkey,
                        filename=filename,
                        current_path=row.current_path,
                        target_path=row.target_path,
                        start_order=row.start_time_us or int(now_mono * 1_000_000),
                        downloaded_bytes=live_bytes,
                        total_bytes=total_bytes,
                        first_seen_at=now_mono,
                        last_active_at=now_mono,
                        missing_since=None,
                    )
                    self._active[tkey] = tracked
                else:
                    tracked.download_id = dl_id
                    tracked.filename = filename
                    tracked.current_path = row.current_path or tracked.current_path
                    tracked.target_path = row.target_path or tracked.target_path
                    if row.start_time_us > tracked.start_order:
                        tracked.start_order = row.start_time_us
                    tracked.downloaded_bytes = live_bytes
                    if total_bytes is not None:
                        tracked.total_bytes = total_bytes
                    tracked.last_active_at = now_mono
                    tracked.missing_since = None

            elif row.state in (
                CHROME_STATE_COMPLETE,
                CHROME_STATE_CANCELLED,
                CHROME_STATE_INTERRUPTED,
            ):
                was_tracked = self._active.pop(tkey, None)
                is_new_since_start = (
                    row.start_time_us >= self._started_webkit_us - 1_000_000
                    and row_id_pair not in self._baseline_row_keys
                    and tkey not in self._finished_keys
                )
                self._baseline_row_keys.add(row_id_pair)
                if was_tracked is None and not is_new_since_start:
                    continue
                self._finished_keys.add(tkey)
                order = was_tracked.start_order if was_tracked is not None else row.start_time_us

                if row.state == CHROME_STATE_COMPLETE:
                    total = (
                        row.total_bytes
                        if row.total_bytes > 0
                        else (was_tracked.total_bytes if was_tracked else row.received_bytes)
                    )
                    dl_bytes = max(row.received_bytes, total or 0)
                    terminal_candidates.append(
                        (
                            order,
                            DownloadSnapshot(
                                state="completed",
                                download_id=was_tracked.download_id if was_tracked else dl_id,
                                filename=filename,
                                downloaded_bytes=dl_bytes,
                                total_bytes=total if total is not None else dl_bytes,
                                progress=100,
                                progress_known=True,
                            ),
                        )
                    )
                elif row.state == CHROME_STATE_CANCELLED:
                    terminal_candidates.append(
                        (
                            order,
                            DownloadSnapshot(
                                state="cancelled",
                                download_id=was_tracked.download_id if was_tracked else dl_id,
                                filename=filename,
                                downloaded_bytes=row.received_bytes,
                                total_bytes=row.total_bytes if row.total_bytes > 0 else None,
                                progress=0,
                                progress_known=False,
                            ),
                        )
                    )
                else:
                    total = (
                        row.total_bytes
                        if row.total_bytes > 0
                        else (was_tracked.total_bytes if was_tracked else None)
                    )
                    dl_bytes = max(
                        row.received_bytes,
                        was_tracked.downloaded_bytes if was_tracked else 0,
                    )
                    pct, known = calculate_download_percent(dl_bytes, total, is_completed=False)
                    terminal_candidates.append(
                        (
                            order,
                            DownloadSnapshot(
                                state="failed",
                                download_id=was_tracked.download_id if was_tracked else dl_id,
                                filename=filename,
                                downloaded_bytes=dl_bytes,
                                total_bytes=total,
                                progress=pct,
                                progress_known=known,
                            ),
                        )
                    )

        # 2. Process any .crdownload files on disk not yet in Chrome's History DB.
        for cr_norm, (cr_path, cr_size, cr_mtime) in crdownload_files.items():
            if cr_norm in matched_crdownloads:
                continue
            target_str = cr_norm[: -len(".crdownload")]
            tkey = os.path.normpath(target_str)
            if tkey in self._finished_keys:
                continue
            ns_entry = nsprogress_map.get(tkey) or nsprogress_map.get(cr_norm)
            ns_completed = ns_entry[0] if ns_entry is not None else 0
            ns_total = ns_entry[1] if ns_entry is not None else None
            live_size = max(cr_size, ns_completed)

            tracked = self._active.get(tkey)
            filename = _display_filename(target_str, cr_norm)
            if tracked is None:
                self._synthetic_seq += 1
                stem = "".join(ch if ch.isalnum() else "-" for ch in Path(target_str).stem)[:24] or "file"
                dl_id = f"crdl-{stem}-{self._synthetic_seq}"
                tracked = _TrackedDownload(
                    download_id=dl_id,
                    target_key=tkey,
                    filename=filename,
                    current_path=str(cr_path),
                    target_path=target_str,
                    start_order=unix_to_webkit_us(cr_mtime),
                    downloaded_bytes=live_size,
                    total_bytes=ns_total,
                    first_seen_at=now_mono,
                    last_active_at=now_mono,
                    missing_since=None,
                )
                self._active[tkey] = tracked
            else:
                tracked.downloaded_bytes = max(tracked.downloaded_bytes, live_size)
                if ns_total is not None and ns_total > 0:
                    tracked.total_bytes = ns_total
                tracked.last_active_at = now_mono
                tracked.missing_since = None

        # 3. Check any remaining tracked downloads whose .crdownload file vanished
        #    without a DB update.
        for tkey in list(self._active.keys()):
            tracked = self._active[tkey]
            cur_norm = os.path.normpath(tracked.current_path) if tracked.current_path else ""
            tgt_cr_norm = os.path.normpath(tracked.target_path + ".crdownload") if tracked.target_path else ""
            if cur_norm in crdownload_files or tgt_cr_norm in crdownload_files:
                continue
            if _safe_file_size(tracked.current_path) is not None and tracked.current_path.endswith(".crdownload"):
                continue

            # Did the final target file appear on disk?
            target_size = _safe_file_size(tracked.target_path) if tracked.target_path else None
            if target_size is not None:
                if tracked.total_bytes is not None and tracked.total_bytes > 0:
                    if target_size >= tracked.total_bytes:
                        self._active.pop(tkey, None)
                        self._finished_keys.add(tkey)
                        terminal_candidates.append(
                            (
                                tracked.start_order,
                                DownloadSnapshot(
                                    state="completed",
                                    download_id=tracked.download_id,
                                    filename=tracked.filename,
                                    downloaded_bytes=target_size,
                                    total_bytes=tracked.total_bytes,
                                    progress=100,
                                    progress_known=True,
                                ),
                            )
                        )
                        continue
                elif target_size >= tracked.downloaded_bytes and (
                    target_size > 0 or tracked.downloaded_bytes == 0
                ):
                    # Verify target file was actually modified after download started.
                    try:
                        tgt_mtime = Path(tracked.target_path).stat().st_mtime
                    except OSError:
                        tgt_mtime = 0.0
                    if tgt_mtime >= self._started_wall - 5.0:
                        self._active.pop(tkey, None)
                        self._finished_keys.add(tkey)
                        terminal_candidates.append(
                            (
                                tracked.start_order,
                                DownloadSnapshot(
                                    state="completed",
                                    download_id=tracked.download_id,
                                    filename=tracked.filename,
                                    downloaded_bytes=target_size,
                                    total_bytes=target_size,
                                    progress=100,
                                    progress_known=True,
                                ),
                            )
                        )
                        continue

            if tracked.missing_since is None:
                # Chrome's temporary 'Unconfirmed <digits>.crdownload' is renamed to
                # '<filename>.crdownload' as soon as headers arrive; drop it silently.
                if _is_unconfirmed_temp(tracked.current_path):
                    self._active.pop(tkey, None)
                    self._finished_keys.add(tkey)
                    continue
                tracked.missing_since = now_mono
            elif now_mono - tracked.missing_since >= self._missing_file_grace_s:
                self._active.pop(tkey, None)
                self._finished_keys.add(tkey)
                terminal_candidates.append(
                    (
                        tracked.start_order,
                        DownloadSnapshot(
                            state="cancelled",
                            download_id=tracked.download_id,
                            filename=tracked.filename,
                            downloaded_bytes=tracked.downloaded_bytes,
                            total_bytes=tracked.total_bytes,
                            progress=0,
                            progress_known=False,
                        ),
                    )
                )

        # 4. Select the focused download according to the Sticky Most-Recently-Started policy.
        if self._active:
            newest_key = max(
                self._active.keys(),
                key=lambda k: (self._active[k].start_order, self._active[k].first_seen_at),
            )
            if self._focused_key is None or self._focused_key not in self._active:
                self._focused_key = newest_key
            else:
                focused = self._active[self._focused_key]
                newest = self._active[newest_key]
                if newest.start_order > focused.start_order:
                    self._focused_key = newest_key

            chosen = self._active[self._focused_key]
            pct, known = calculate_download_percent(
                chosen.downloaded_bytes,
                chosen.total_bytes,
                is_completed=False,
            )
            # While still in progress on disk, clamp 100% to 99% until actual completion.
            if known and pct >= 100:
                pct = 99
            state = "starting" if chosen.downloaded_bytes == 0 else "downloading"
            return DownloadSnapshot(
                state=state,
                download_id=chosen.download_id,
                filename=chosen.filename,
                downloaded_bytes=chosen.downloaded_bytes,
                total_bytes=chosen.total_bytes,
                progress=pct,
                progress_known=known,
            )

        self._focused_key = None
        if terminal_candidates:
            terminal_candidates.sort(key=lambda item: item[0], reverse=True)
            return terminal_candidates[0][1]

        return DownloadSnapshot(state="idle")


def build_download_message(
    snapshot: DownloadSnapshot,
    *,
    now: datetime | None = None,
    include_filename: bool = False,
) -> dict:
    """Turn a ``DownloadSnapshot`` into a validated ``/v1/download`` message."""
    moment = now or datetime.now(timezone.utc)
    payload: dict = {
        "schema_version": 1,
        "kind": "download",
        "download_id": snapshot.download_id,
        "state": snapshot.state,
        "downloaded_bytes": snapshot.downloaded_bytes,
        "total_bytes": snapshot.total_bytes,
        "progress": snapshot.progress,
        "progress_known": snapshot.progress_known,
        "timestamp": format_timestamp(moment),
    }
    if include_filename and snapshot.filename:
        payload["filename"] = snapshot.filename
    return validate_download_message(payload)


class DownloadReporter:
    """Poll a download detector and send deduplicated updates to the UNO Q receiver.

    Avoids sending repeated identical percentages (e.g., 43%, 43%, 43%) and
    suppresses idle spam when no download is active.
    """

    def __init__(
        self,
        send_fn,
        *,
        read_fn,
    ) -> None:
        self._send_fn = send_fn
        self._read_fn = read_fn
        self._last_sent_key: tuple | None = None
        self._had_active_download: bool = False

    def poll_once(self, *, force: bool = False) -> dict:
        snapshot: DownloadSnapshot = self._read_fn()
        if snapshot.state == "idle":
            if not self._had_active_download and not force:
                return {
                    "status": "idle",
                    "sent": False,
                    "snapshot": snapshot,
                }
            # After a completed or failed download was already sent, the receiver's
            # StateEngine automatically holds the final cue briefly and returns to
            # normal mode via tick(). Do not immediately overwrite that hold with idle.
            if (
                self._last_sent_key is not None
                and self._last_sent_key[1] in {"completed", "failed"}
                and not force
            ):
                self._had_active_download = False
                return {
                    "status": "idle",
                    "sent": False,
                    "snapshot": snapshot,
                }

        effective_state = (
            "downloading"
            if snapshot.state in {"starting", "downloading"}
            else snapshot.state
        )
        key = (
            snapshot.download_id,
            effective_state,
            snapshot.progress,
            snapshot.progress_known,
        )
        if not force and key == self._last_sent_key:
            return {
                "status": "unchanged",
                "sent": False,
                "snapshot": snapshot,
            }

        message = build_download_message(snapshot)
        result = self._send_fn(message)
        delivered = bool(result.get("delivered"))
        if delivered:
            self._last_sent_key = key
            if snapshot.state in {"starting", "downloading"}:
                self._had_active_download = True
            elif snapshot.state in {"idle", "completed", "failed", "cancelled"}:
                self._had_active_download = False

        return {
            "status": "sent" if delivered else "delivery_failed",
            "sent": delivered,
            "snapshot": snapshot,
            "message": message,
            "delivery": result,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Monitor Google Chrome downloads on macOS and send progress to the UNO Q receiver"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.25,
        help="Seconds between download checks (default 0.25s = 4 Hz).",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Check once, send if active (or with --dry-run print JSON), then exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the validated download JSON locally without contacting the board.",
    )
    parser.add_argument(
        "--chrome-dir",
        default=None,
        help="Optional override for Chrome user data directory.",
    )
    parser.add_argument(
        "--downloads-dir",
        default=None,
        help="Optional override for macOS Downloads directory (defaults to ~/Downloads).",
    )
    parser.add_argument("--url", default=None)
    parser.add_argument("--token", default=None)
    parser.add_argument("--config", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.interval <= 0:
        print("--interval must be greater than 0", file=sys.stderr)
        return 2

    detector = ChromeDownloadDetector(
        chrome_root=Path(args.chrome_dir) if args.chrome_dir else None,
        downloads_dir=Path(args.downloads_dir) if args.downloads_dir else None,
    )

    if args.dry_run:
        snapshot = detector.poll()
        msg = build_download_message(snapshot)
        print(json.dumps(msg), flush=True)
        return 0

    try:
        base_url, token = resolve_target(args)
    except ProtocolError as exc:
        print(exc.detail, file=sys.stderr)
        return 2

    reporter = DownloadReporter(
        lambda msg: post_download(base_url, token, msg),
        read_fn=detector.poll,
    )

    print(
        f"Monitoring Chrome downloads (polling every {args.interval:.2f}s) -> {base_url}",
        flush=True,
    )
    try:
        while True:
            outcome = reporter.poll_once()
            status = outcome["status"]
            snap: DownloadSnapshot = outcome["snapshot"]
            if status == "sent":
                pct_str = f"{snap.progress}%" if snap.progress_known else "indeterminate"
                name_note = f" [{snap.filename}]" if snap.filename else ""
                print(
                    f"download {snap.state} {pct_str}{name_note} -> accepted",
                    flush=True,
                )
            elif status == "delivery_failed":
                delivery = outcome.get("delivery", {})
                print(
                    f"download delivery {delivery.get('delivery')}: {delivery.get('detail')}",
                    file=sys.stderr,
                )
            if args.once:
                return 0 if status in {"sent", "unchanged", "idle"} else 1
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nDownload monitor stopped.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
