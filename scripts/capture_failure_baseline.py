#!/usr/bin/env python3
"""Capture real failure logs for the Gemma evidence baseline.

Runs the failure commands this project already knows how to classify and
stores the original stderr/stdout. The on-disk history database is included
when it has rows, but those rows currently have empty excerpts, so they are
not treated as log text.

The captured text is passed through the existing redactor before it is written.
"""

from __future__ import annotations

import json
import os
import sqlite3
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))

from excerpt import redact  # noqa: E402
from explainer import explain_failure  # noqa: E402

OUT = ROOT / "shared" / "fixtures" / "failure_baseline.json"
HISTORY_DB = Path(os.environ.get("STILL_LOADING_DB", Path.home() / ".still_loading_history.db"))
PYTHON = sys.executable


def _run(argv: list[str], *, cwd: str | None = None) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        err = exc.stderr or ""
        out = exc.stdout or ""
        if isinstance(err, bytes):
            err = err.decode("utf-8", errors="replace")
        if isinstance(out, bytes):
            out = out.decode("utf-8", errors="replace")
        return 124, redact((err or out or "TimeoutExpired").strip())
    except FileNotFoundError as exc:
        return 127, redact(f"{exc.__class__.__name__}: {exc}")
    except PermissionError as exc:
        return 126, redact(f"{exc.__class__.__name__}: {exc}")
    text = (completed.stderr or "").strip()
    if not text:
        text = (completed.stdout or "").strip()
    return completed.returncode, redact(text)


def _commands(workdir: Path) -> list[tuple[str, list[str]]]:
    syntax_file = workdir / "broken_syntax.py"
    syntax_file.write_text("def broken(\n    return 1\n", encoding="utf-8")
    indent_file = workdir / "broken_indent.py"
    indent_file.write_text("def broken():\nreturn 1\n", encoding="utf-8")
    locked = workdir / "locked.txt"
    locked.write_text("hidden\n", encoding="utf-8")
    os.chmod(locked, 0)
    script = workdir / "not_executable.sh"
    script.write_text("#!/bin/sh\necho no\n", encoding="utf-8")
    os.chmod(script, stat.S_IRUSR | stat.S_IWUSR)
    test_file = workdir / "test_fail_sample.py"
    test_file.write_text(
        "import unittest\n"
        "class Sample(unittest.TestCase):\n"
        "    def test_progress(self):\n"
        "        self.assertEqual(1, 2)\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n",
        encoding="utf-8",
    )
    missing = workdir / "does-not-exist.txt"
    return [
        ("python_missing_module", [PYTHON, "-c", "import non_existent_pkg_xyz"]),
        ("python_syntax_error", [PYTHON, str(syntax_file)]),
        ("python_indentation_error", [PYTHON, str(indent_file)]),
        ("python_file_not_found", [PYTHON, "-c", f"open({str(missing)!r})"]),
        ("python_permission_denied", [PYTHON, "-c", f"open({str(locked)!r})"]),
        ("python_zero_division", [PYTHON, "-c", "print(1/0)"]),
        ("python_type_error", [PYTHON, "-c", "len(None)"]),
        ("python_value_error", [PYTHON, "-c", "int('not-a-number')"]),
        ("python_key_error", [PYTHON, "-c", "print({}['missing'])"]),
        ("python_index_error", [PYTHON, "-c", "print([][0])"]),
        ("python_attribute_error", [PYTHON, "-c", "None.missing"]),
        ("python_assertion", [PYTHON, "-c", "assert False, 'expected progress 100'"]),
        ("python_memory_error", [PYTHON, "-c", "raise MemoryError('allocation failed')"]),
        (
            "python_connection_refused",
            [PYTHON, "-c", "import socket; socket.create_connection(('127.0.0.1', 1), timeout=0.4)"],
        ),
        (
            "python_receiver_url_error",
            [PYTHON, "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9', timeout=0.4)"],
        ),
        ("python_missing_binary", [PYTHON, "-c", "import os; os.execvp('still-loading-missing-bin', ['still-loading-missing-bin'])"]),
        ("script_not_executable", [str(script)]),
        ("node_missing_module", ["node", "-e", "require('module-that-does-not-exist-still-loading')"]),
        ("git_not_a_repository", ["git", "-C", str(workdir / "not-a-git-repo"), "status"]),
        ("python_unittest_failure", [PYTHON, "-m", "unittest", "test_fail_sample"]),
    ]


def _history_cases() -> list[dict]:
    if not HISTORY_DB.is_file():
        return []
    cases = []
    conn = sqlite3.connect(f"file:{HISTORY_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT job_id, event, exit_code, message, category, summary, suggestion, excerpt "
            "FROM job_history WHERE is_failure = 1"
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    for row in rows:
        excerpt = redact((row["excerpt"] or "").strip())
        message = redact((row["message"] or "").strip())
        log = excerpt or message
        if not log:
            continue
        cases.append(
            {
                "id": f"history_{row['job_id']}",
                "source": "history_store",
                "command": [],
                "exit_code": row["exit_code"] if row["exit_code"] is not None else 1,
                "log": log,
                "history_category": row["category"],
                "history_summary": row["summary"],
                "history_suggestion": row["suggestion"],
                "note": "Stored job row. Excerpt was empty, so the original failure message is the log text.",
            }
        )
    return cases


def main() -> int:
    cases: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="still-loading-baseline-") as raw:
        workdir = Path(raw)
        (workdir / "not-a-git-repo").mkdir()
        command_list = _commands(workdir)
        for case_id, argv in command_list:
            code, log = _run(argv, cwd=str(workdir))
            if not log:
                continue
            explanation = explain_failure(exit_code=code or 1, message=f"exit {code}", excerpt=log)
            # Keep commands portable: drop absolute temp paths from the command list
            # but keep the original log text, which is the evidence.
            cases.append(
                {
                    "id": case_id,
                    "source": "captured_process",
                    "command": [Path(part).name if str(workdir) in part else part for part in argv],
                    "exit_code": code,
                    "log": log,
                    "expected_category": explanation.category,
                    "expected_summary": explanation.summary,
                    "expected_suggestion": explanation.suggestion,
                }
            )
        locked = workdir / "locked.txt"
        if locked.exists():
            os.chmod(locked, stat.S_IRUSR | stat.S_IWUSR)
    history = _history_cases()
    payload = {
        "description": (
            "Real failure logs for Gemma evidence checks. Each process case is the "
            "original stderr or stdout of a command run on this machine, then passed "
            "through the project redactor. The local history database had failed jobs "
            "but empty excerpts, so those rows are recorded only as a note and are not "
            "used as log evidence."
        ),
        "history_rows_without_excerpts": [
            {"id": item["id"], "message": item["log"]} for item in history
        ],
        "case_count": len(cases),
        "cases": cases,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(cases)} cases to {OUT}")
    return 0 if len(cases) >= 15 else 1


if __name__ == "__main__":
    raise SystemExit(main())
