"""Phase 6 tests: excerpt extraction, redaction, and wire integration.

Covers:
- Tail line extraction with byte and line limits
- Secret redaction (bearer tokens, env vars, hex strings)
- Stderr-preferred fallback to stdout
- Wire validation of the optional excerpt field
- Process runner attaches excerpts on failure
- Job snapshot surfaces the excerpt
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

MAC_AGENT = Path(__file__).resolve().parent.parent
ROOT = MAC_AGENT.parent
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(MAC_AGENT))

from excerpt import (
    MAX_EXCERPT_BYTES,
    MAX_EXCERPT_LINES,
    extract_excerpt,
    redact,
    safe_excerpt_for_event,
)
from messages import JobLog, ProtocolError, validate_message
from runner import run_process
from simulator import format_timestamp

from datetime import datetime, timezone


def _make_failed(
    *,
    job_id: str = "test-job",
    sequence: int = 1,
    exit_code: int = 1,
    message: str = "Process exited with code 1",
    excerpt: str | None = None,
) -> dict:
    """Construct a minimal valid failed event for testing."""
    event: dict = {
        "schema_version": 1,
        "event": "failed",
        "job_id": job_id,
        "sequence": sequence,
        "timestamp": format_timestamp(datetime.now(timezone.utc)),
        "elapsed_seconds": 5.0,
        "progress": 0,
        "is_failure": True,
        "exit_code": exit_code,
        "message": message,
    }
    if excerpt is not None:
        event["excerpt"] = excerpt
    return event


class RedactionTests(unittest.TestCase):
    """Secret values are scrubbed from excerpts."""

    def test_bearer_token_is_redacted(self) -> None:
        line = "Authorization: Bearer e51c5d87976dfcfccb521f2f11d2a63b"
        result = redact(line)
        self.assertNotIn("e51c5d87976dfcfccb521f2f11d2a63b", result)
        self.assertIn("[REDACTED]", result)

    def test_bearer_case_insensitive(self) -> None:
        line = "bearer MySecretToken123456789012"
        result = redact(line)
        self.assertNotIn("MySecretToken123456789012", result)

    def test_env_var_token_redacted(self) -> None:
        line = "export STILL_LOADING_TOKEN='e51c5d87976dfcfccb521f2f11d2a63b'"
        result = redact(line)
        self.assertNotIn("e51c5d87976dfcfccb521f2f11d2a63b", result)
        self.assertIn("[REDACTED]", result)

    def test_password_assignment_redacted(self) -> None:
        line = "DB_PASSWORD=hunter2"
        result = redact(line)
        self.assertNotIn("hunter2", result)

    def test_api_key_redacted(self) -> None:
        line = 'API_KEY="sk-abc123xyz789"'
        result = redact(line)
        self.assertNotIn("sk-abc123xyz789", result)

    def test_long_hex_redacted(self) -> None:
        hex_token = "a" * 32
        line = f"Token is {hex_token} and that is final"
        result = redact(line)
        self.assertNotIn(hex_token, result)
        self.assertIn("[REDACTED_HEX]", result)

    def test_short_hex_not_redacted(self) -> None:
        """Exit codes and short hex strings are not touched."""
        line = "exit code 0xff00"
        result = redact(line)
        self.assertEqual(line, result)

    def test_normal_error_text_unchanged(self) -> None:
        line = "FileNotFoundError: [Errno 2] No such file or directory: 'missing.txt'"
        result = redact(line)
        self.assertEqual(line, result)


class ExcerptExtractionTests(unittest.TestCase):
    """Tail extraction with line and byte limits."""

    def test_empty_output_returns_empty(self) -> None:
        self.assertEqual(extract_excerpt("", ""), "")

    def test_whitespace_only_returns_empty(self) -> None:
        self.assertEqual(extract_excerpt("  \n\n  ", "  \n\n  "), "")

    def test_stderr_preferred_over_stdout(self) -> None:
        result = extract_excerpt("stdout line", "stderr line")
        self.assertIn("stderr", result)
        self.assertNotIn("stdout", result)

    def test_stdout_fallback_when_stderr_empty(self) -> None:
        result = extract_excerpt("stdout fallback", "")
        self.assertIn("stdout fallback", result)

    def test_line_limit(self) -> None:
        lines = "\n".join(f"line {i}" for i in range(20))
        result = extract_excerpt("", lines, max_lines=5)
        self.assertEqual(result.count("\n"), 4)  # 5 lines, 4 newlines
        self.assertIn("line 19", result)
        self.assertNotIn("line 0", result)

    def test_byte_limit(self) -> None:
        lines = "\n".join(f"{'x' * 50} line {i}" for i in range(30))
        result = extract_excerpt("", lines, max_bytes=200)
        self.assertLessEqual(len(result.encode("utf-8")), 200 + 50)  # small overshoot tolerance
        self.assertIn("line 29", result)

    def test_secrets_redacted_in_excerpt(self) -> None:
        stderr = "export TOKEN=secretvalue123456789012345678901234567890\nSegmentation fault"
        result = extract_excerpt("", stderr)
        self.assertNotIn("secretvalue", result)
        self.assertIn("Segmentation fault", result)

    def test_safe_excerpt_returns_none_when_empty(self) -> None:
        self.assertIsNone(safe_excerpt_for_event("", ""))

    def test_safe_excerpt_returns_string_when_present(self) -> None:
        result = safe_excerpt_for_event("", "error: bad flag")
        self.assertIsInstance(result, str)
        self.assertIn("bad flag", result)


class WireValidationTests(unittest.TestCase):
    """The optional excerpt field on failed events."""

    def test_failed_with_excerpt_accepted(self) -> None:
        event = _make_failed(excerpt="Traceback: something went wrong")
        result = validate_message(event)
        self.assertEqual(result["excerpt"], "Traceback: something went wrong")

    def test_failed_without_excerpt_accepted(self) -> None:
        event = _make_failed()
        result = validate_message(event)
        self.assertNotIn("excerpt", result)

    def test_excerpt_too_long_rejected(self) -> None:
        event = _make_failed(excerpt="x" * 513)
        with self.assertRaises(ProtocolError) as ctx:
            validate_message(event)
        self.assertIn("512", ctx.exception.detail)

    def test_excerpt_wrong_type_rejected(self) -> None:
        event = _make_failed(excerpt=42)
        with self.assertRaises(ProtocolError):
            validate_message(event)

    def test_excerpt_on_non_failed_event_rejected(self) -> None:
        event = {
            "schema_version": 1,
            "event": "heartbeat",
            "job_id": "test-job",
            "sequence": 1,
            "timestamp": format_timestamp(datetime.now(timezone.utc)),
            "elapsed_seconds": 2.0,
            "progress": 0,
            "is_failure": False,
            "excerpt": "should not be here",
        }
        with self.assertRaises(ProtocolError) as ctx:
            validate_message(event)
        self.assertIn("excerpt", ctx.exception.detail)

    def test_excerpt_on_completed_event_rejected(self) -> None:
        event = {
            "schema_version": 1,
            "event": "completed",
            "job_id": "test-job",
            "sequence": 1,
            "timestamp": format_timestamp(datetime.now(timezone.utc)),
            "elapsed_seconds": 20.0,
            "progress": 100,
            "is_failure": False,
            "exit_code": 0,
            "excerpt": "should not be here",
        }
        with self.assertRaises(ProtocolError) as ctx:
            validate_message(event)
        self.assertIn("excerpt", ctx.exception.detail)

    def test_excerpt_max_length_accepted(self) -> None:
        event = _make_failed(excerpt="x" * 512)
        result = validate_message(event)
        self.assertEqual(len(result["excerpt"]), 512)

    def test_excerpt_empty_string_accepted(self) -> None:
        """An empty string excerpt is valid but pointless; the runner avoids it."""
        event = _make_failed(excerpt="")
        result = validate_message(event)
        self.assertEqual(result["excerpt"], "")


class JobLogSnapshotTests(unittest.TestCase):
    """The job snapshot surfaces the excerpt at the top level."""

    def test_snapshot_includes_excerpt_on_failure(self) -> None:
        log = JobLog()
        event = _make_failed(excerpt="ImportError: no module named foo")
        log.accept(event)
        snap = log.snapshot("test-job")
        self.assertIsNotNone(snap)
        self.assertEqual(snap["excerpt"], "ImportError: no module named foo")
        self.assertEqual(snap["latest"]["excerpt"], "ImportError: no module named foo")

    def test_snapshot_no_excerpt_on_success(self) -> None:
        log = JobLog()
        started = {
            "schema_version": 1,
            "event": "started",
            "job_id": "ok-job",
            "sequence": 1,
            "timestamp": format_timestamp(datetime.now(timezone.utc)),
            "elapsed_seconds": 0.0,
            "progress": 0,
            "is_failure": False,
        }
        log.accept(started)
        snap = log.snapshot("ok-job")
        self.assertNotIn("excerpt", snap)


class ProcessRunnerExcerptTests(unittest.TestCase):
    """The process runner attaches excerpts to failed events."""

    def test_failing_process_includes_excerpt(self) -> None:
        record = run_process(
            [sys.executable, "-c", "import sys; print('oops', file=sys.stderr); sys.exit(1)"],
            heartbeat_interval=0.5,
        )
        self.assertNotEqual(record.exit_code, 0)
        failed_events = [e for e in record.events if e["event"] == "failed"]
        self.assertEqual(len(failed_events), 1)
        self.assertIn("excerpt", failed_events[0])
        self.assertIn("oops", failed_events[0]["excerpt"])

    def test_succeeding_process_has_no_excerpt(self) -> None:
        record = run_process(
            [sys.executable, "-c", "print('hello')"],
            heartbeat_interval=0.5,
        )
        self.assertEqual(record.exit_code, 0)
        completed_events = [e for e in record.events if e["event"] == "completed"]
        self.assertEqual(len(completed_events), 1)
        self.assertNotIn("excerpt", completed_events[0])

    def test_failing_process_redacts_secrets_in_excerpt(self) -> None:
        # Print a fake bearer token to stderr, then fail
        code = (
            "import sys; "
            "print('Authorization: Bearer e51c5d87976dfcfccb521f2f11d2a63b', file=sys.stderr); "
            "sys.exit(1)"
        )
        record = run_process(
            [sys.executable, "-c", code],
            heartbeat_interval=0.5,
        )
        failed = [e for e in record.events if e["event"] == "failed"]
        self.assertEqual(len(failed), 1)
        excerpt = failed[0].get("excerpt", "")
        self.assertNotIn("e51c5d87976dfcfccb521f2f11d2a63b", excerpt)
        self.assertIn("[REDACTED]", excerpt)

    def test_quiet_failure_has_no_excerpt(self) -> None:
        """A process that prints nothing and fails still produces no excerpt."""
        record = run_process(
            [sys.executable, "-c", "import sys; sys.exit(2)"],
            heartbeat_interval=0.5,
        )
        self.assertNotEqual(record.exit_code, 0)
        failed = [e for e in record.events if e["event"] == "failed"]
        self.assertEqual(len(failed), 1)
        # No output means no excerpt (omitted, not empty string)
        self.assertNotIn("excerpt", failed[0])


if __name__ == "__main__":
    unittest.main()
