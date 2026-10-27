"""Phase 7 tests: rules-based failure explanations, feasibility check, and wire integration.

Covers:
- Signal-based explanation inference (126, 127, 130, 137, 139, 143)
- Language & ecosystem error pattern matching (Python, Node.js, Rust, C/C++, Git, Docker)
- Fallback explanations for unknown exit codes & excerpts
- Wire message validation of the explanation dictionary
- JobLog snapshot surfacing and dynamic generation
- Process runner end-to-end explanation attachment
- Model feasibility hardware detection and report generation
"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

MAC_AGENT = Path(__file__).resolve().parent.parent
ROOT = MAC_AGENT.parent
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(MAC_AGENT))

from explainer import FailureExplanation, explain_failure
from messages import JobLog, ProtocolError, validate_message
from model_feasibility import assess_feasibility, get_hardware_profile
from runner import run_process
from simulator import format_timestamp


def _make_failed(
    *,
    job_id: str = "test-job",
    sequence: int = 1,
    exit_code: int = 1,
    message: str = "Process exited with code 1",
    excerpt: str | None = None,
    explanation: dict | None = None,
) -> dict:
    event: dict = {
        "schema_version": 1,
        "event": "failed",
        "job_id": job_id,
        "sequence": sequence,
        "timestamp": format_timestamp(datetime.now(timezone.utc)),
        "elapsed_seconds": 3.0,
        "progress": 0,
        "is_failure": True,
        "exit_code": exit_code,
        "message": message,
    }
    if excerpt is not None:
        event["excerpt"] = excerpt
    if explanation is not None:
        event["explanation"] = explanation
    return event


class SignalExplanationTests(unittest.TestCase):
    """Signal exit code analysis."""

    def test_permission_denied_exit_126(self) -> None:
        exp = explain_failure(exit_code=126)
        self.assertEqual(exp.category, "permission_denied")
        self.assertIn("permission denied", exp.summary.lower())
        self.assertIn("chmod", exp.suggestion)
        self.assertEqual(exp.confidence, 0.7)

    def test_command_not_found_exit_127(self) -> None:
        exp = explain_failure(exit_code=127)
        self.assertEqual(exp.category, "command_not_found")
        self.assertIn("command not found", exp.summary.lower())
        self.assertIn("$PATH", exp.suggestion)

    def test_interrupted_exit_130(self) -> None:
        exp = explain_failure(exit_code=130)
        self.assertEqual(exp.category, "interrupted")
        self.assertIn("SIGINT", exp.summary)

    def test_oom_killed_exit_137(self) -> None:
        exp = explain_failure(exit_code=137)
        self.assertEqual(exp.category, "out_of_memory")
        self.assertIn("SIGKILL", exp.summary)

    def test_segfault_exit_139(self) -> None:
        exp = explain_failure(exit_code=139)
        self.assertEqual(exp.category, "segmentation_fault")
        self.assertIn("SIGSEGV", exp.summary)

    def test_sigterm_exit_143(self) -> None:
        exp = explain_failure(exit_code=143)
        self.assertEqual(exp.category, "terminated")
        self.assertIn("SIGTERM", exp.summary)


class PatternExplanationTests(unittest.TestCase):
    """Pattern matching from failure log excerpts."""

    def test_python_missing_module(self) -> None:
        excerpt = "ModuleNotFoundError: No module named 'numpy'"
        exp = explain_failure(exit_code=1, excerpt=excerpt)
        self.assertEqual(exp.category, "missing_dependency")
        self.assertIn("numpy", exp.summary)
        self.assertIn("pip install numpy", exp.suggestion)
        self.assertEqual(exp.confidence, 1.0)

    def test_python_import_error(self) -> None:
        excerpt = "ImportError: cannot import name 'foo' from 'requests'"
        exp = explain_failure(exit_code=1, excerpt=excerpt)
        self.assertEqual(exp.category, "missing_dependency")
        self.assertIn("requests", exp.summary)

    def test_python_syntax_error(self) -> None:
        excerpt = "SyntaxError: unexpected EOF while parsing"
        exp = explain_failure(exit_code=1, excerpt=excerpt)
        self.assertEqual(exp.category, "syntax_error")
        self.assertIn("unexpected EOF", exp.summary)

    def test_python_indentation_error(self) -> None:
        excerpt = "IndentationError: expected an indented block after 'if' statement"
        exp = explain_failure(exit_code=1, excerpt=excerpt)
        self.assertEqual(exp.category, "syntax_error")
        self.assertIn("indented block", exp.summary)

    def test_python_file_not_found(self) -> None:
        excerpt = "FileNotFoundError: [Errno 2] No such file or directory: 'data/input.csv'"
        exp = explain_failure(exit_code=1, excerpt=excerpt)
        self.assertEqual(exp.category, "file_not_found")
        self.assertIn("data/input.csv", exp.summary)

    def test_python_zero_division(self) -> None:
        excerpt = "ZeroDivisionError: division by zero"
        exp = explain_failure(exit_code=1, excerpt=excerpt)
        self.assertEqual(exp.category, "runtime_error")
        self.assertIn("Division by zero", exp.summary)

    def test_python_type_error(self) -> None:
        excerpt = "TypeError: can only concatenate str (not 'int') to str"
        exp = explain_failure(exit_code=1, excerpt=excerpt)
        self.assertEqual(exp.category, "runtime_error")
        self.assertIn("TypeError", exp.summary)

    def test_test_assertion_failure(self) -> None:
        excerpt = "FAILED (failures=2, errors=0)"
        exp = explain_failure(exit_code=1, excerpt=excerpt)
        self.assertEqual(exp.category, "test_failure")

    def test_node_missing_module(self) -> None:
        excerpt = "Error: Cannot find module 'express'"
        exp = explain_failure(exit_code=1, excerpt=excerpt)
        self.assertEqual(exp.category, "missing_dependency")
        self.assertIn("express", exp.summary)
        self.assertIn("npm install express", exp.suggestion)

    def test_rust_compiler_error(self) -> None:
        excerpt = "error[E0382]: use of moved value: `s`"
        exp = explain_failure(exit_code=101, excerpt=excerpt)
        self.assertEqual(exp.category, "compiler_error")
        self.assertIn("E0382", exp.summary)
        self.assertIn("rustc --explain E0382", exp.suggestion)

    def test_c_missing_header(self) -> None:
        excerpt = "fatal error: openssl/ssl.h: No such file or directory"
        exp = explain_failure(exit_code=1, excerpt=excerpt)
        self.assertEqual(exp.category, "missing_dependency")
        self.assertIn("openssl/ssl.h", exp.summary)

    def test_network_connection_refused(self) -> None:
        excerpt = "ConnectionRefusedError: [Errno 61] Connection refused"
        exp = explain_failure(exit_code=1, excerpt=excerpt)
        self.assertEqual(exp.category, "network_error")

    def test_git_merge_conflict(self) -> None:
        excerpt = "CONFLICT (content): Merge conflict in src/main.py"
        exp = explain_failure(exit_code=1, excerpt=excerpt)
        self.assertEqual(exp.category, "merge_conflict")
        self.assertIn("src/main.py", exp.summary)

    def test_docker_daemon_not_running(self) -> None:
        excerpt = "Cannot connect to the Docker daemon at unix:///var/run/docker.sock"
        exp = explain_failure(exit_code=1, excerpt=excerpt)
        self.assertEqual(exp.category, "docker_error")


class FallbackExplanationTests(unittest.TestCase):
    """Fallback explanations for unpatterned errors."""

    def test_excerpt_last_line_extracted(self) -> None:
        excerpt = "Step 1: ok\nStep 2: failed because build script exited abnormally"
        exp = explain_failure(exit_code=42, excerpt=excerpt)
        self.assertEqual(exp.category, "generic_error")
        self.assertIn("build script exited abnormally", exp.summary)
        self.assertEqual(exp.confidence, 0.5)

    def test_no_excerpt_generic_fallback(self) -> None:
        exp = explain_failure(exit_code=99, message="Custom failure message")
        self.assertEqual(exp.category, "generic_error")
        self.assertEqual(exp.summary, "Custom failure message")
        self.assertEqual(exp.confidence, 0.3)


class WireValidationTests(unittest.TestCase):
    """Wire validation of the explanation field."""

    def test_failed_with_explanation_accepted(self) -> None:
        exp = {
            "category": "missing_dependency",
            "summary": "Missing Python module: 'requests'",
            "suggestion": "pip install requests",
            "confidence": 1.0,
            "source": "rules",
        }
        event = _make_failed(explanation=exp)
        result = validate_message(event)
        self.assertEqual(result["explanation"]["category"], "missing_dependency")

    def test_explanation_on_completed_event_rejected(self) -> None:
        event = {
            "schema_version": 1,
            "event": "completed",
            "job_id": "ok-job",
            "sequence": 1,
            "timestamp": format_timestamp(datetime.now(timezone.utc)),
            "elapsed_seconds": 10.0,
            "progress": 100,
            "is_failure": False,
            "exit_code": 0,
            "explanation": {"category": "none", "summary": "none", "suggestion": "none"},
        }
        with self.assertRaises(ProtocolError) as ctx:
            validate_message(event)
        self.assertIn("explanation", ctx.exception.detail)

    def test_explanation_on_heartbeat_rejected(self) -> None:
        event = {
            "schema_version": 1,
            "event": "heartbeat",
            "job_id": "test-job",
            "sequence": 1,
            "timestamp": format_timestamp(datetime.now(timezone.utc)),
            "elapsed_seconds": 2.0,
            "progress": 0,
            "is_failure": False,
            "explanation": {"category": "test", "summary": "test", "suggestion": "test"},
        }
        with self.assertRaises(ProtocolError) as ctx:
            validate_message(event)
        self.assertIn("explanation", ctx.exception.detail)

    def test_explanation_non_dict_rejected(self) -> None:
        event = _make_failed(explanation="not a dict")  # type: ignore
        with self.assertRaises(ProtocolError) as ctx:
            validate_message(event)
        self.assertIn("explanation", ctx.exception.detail)


class JobLogSnapshotExplanationTests(unittest.TestCase):
    """Snapshot surfaces existing and dynamically generated explanations."""

    def test_snapshot_includes_wire_explanation(self) -> None:
        log = JobLog()
        exp = {
            "category": "syntax_error",
            "summary": "Syntax error",
            "suggestion": "Fix line 10",
        }
        event = _make_failed(explanation=exp)
        log.accept(event)
        snap = log.snapshot("test-job")
        self.assertIsNotNone(snap)
        self.assertEqual(snap["explanation"]["category"], "syntax_error")

    def test_snapshot_generates_explanation_when_missing(self) -> None:
        log = JobLog()
        # Failed event with excerpt but no explanation
        event = _make_failed(excerpt="ModuleNotFoundError: No module named 'flask'")
        log.accept(event)
        snap = log.snapshot("test-job")
        self.assertIsNotNone(snap)
        self.assertIn("explanation", snap)
        self.assertEqual(snap["explanation"]["category"], "missing_dependency")
        self.assertIn("flask", snap["explanation"]["summary"])


class ProcessRunnerExplanationTests(unittest.TestCase):
    """Process runner attaches explanations to failing commands."""

    def test_failing_process_includes_explanation(self) -> None:
        # Command failing with a python ImportError
        cmd = [sys.executable, "-c", "import non_existent_pkg_xyz"]
        record = run_process(cmd, heartbeat_interval=0.5)
        self.assertNotEqual(record.exit_code, 0)
        failed_event = record.events[-1]
        self.assertEqual(failed_event["event"], "failed")
        self.assertIn("explanation", failed_event)
        exp = failed_event["explanation"]
        self.assertEqual(exp["category"], "missing_dependency")
        self.assertIn("non_existent_pkg_xyz", exp["summary"])
        self.assertIn("pip install", exp["suggestion"])

    def test_succeeding_process_has_no_explanation(self) -> None:
        record = run_process([sys.executable, "-c", "print('ok')"], heartbeat_interval=0.5)
        self.assertEqual(record.exit_code, 0)
        completed_event = record.events[-1]
        self.assertNotIn("explanation", completed_event)


class FeasibilityTests(unittest.TestCase):
    """Feasibility hardware check and report."""

    def test_hardware_profile_detection(self) -> None:
        p = get_hardware_profile()
        self.assertGreater(p.cpu_count, 0)
        self.assertGreater(p.total_memory_mb, 0)
        self.assertIn(p.platform_system, ["Darwin", "Linux", "Windows"])

    def test_assess_feasibility_returns_report(self) -> None:
        report = assess_feasibility()
        self.assertIn(report.recommended_engine, ["rules", "rules_with_mac_optional", "local_slm"])
        self.assertIsInstance(report.can_safely_load_500m_model, bool)
        self.assertGreater(report.estimated_tokens_per_second, 0.0)


if __name__ == "__main__":
    unittest.main()
