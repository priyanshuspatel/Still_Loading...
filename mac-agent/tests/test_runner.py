"""Local process runner. These tests do not open a socket."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "mac-agent"))

from messages import validate_message  # noqa: E402
from runner import run_process  # noqa: E402
from run_job import command_argv, main  # noqa: E402

PYTHON = sys.executable


def names(events: list[dict]) -> list[str]:
    return [event["event"] for event in events]


class ProcessRunnerTests(unittest.TestCase):
    def test_quiet_process_completes_without_a_failure(self) -> None:
        record = run_process(
            [PYTHON, "-c", "import time; time.sleep(0.4)"],
            heartbeat_interval=0.1,
            job_id="quietjob",
        )
        self.assertEqual(record.exit_code, 0)
        self.assertIsNotNone(record.pid)
        self.assertGreater(record.pid, 0)
        self.assertEqual(record.stdout, "")
        self.assertEqual(record.stderr, "")
        self.assertEqual(names(record.events)[0], "started")
        self.assertIn("heartbeat", names(record.events))
        self.assertNotIn("progress", names(record.events))
        self.assertEqual(record.events[-1]["event"], "completed")
        self.assertEqual(record.events[-1]["exit_code"], 0)
        self.assertEqual(record.events[-1]["progress"], 100)
        self.assertFalse(record.events[-1]["is_failure"])
        for event in record.events:
            validate_message(event)
            self.assertEqual(event["source"], "process")

    def test_stdout_and_stderr_stay_separate(self) -> None:
        record = run_process(
            [
                PYTHON,
                "-c",
                "import sys; print('OUT-ONLY'); sys.stderr.write('ERR-ONLY\\n')",
            ],
            heartbeat_interval=2,
            job_id="splitjob",
        )
        self.assertEqual(record.exit_code, 0)
        self.assertIn("OUT-ONLY", record.stdout)
        self.assertNotIn("ERR-ONLY", record.stdout)
        self.assertIn("ERR-ONLY", record.stderr)
        self.assertNotIn("OUT-ONLY", record.stderr)
        self.assertEqual(record.events[-1]["event"], "completed")

    def test_nonzero_exit_is_failed_and_hides_stream_text(self) -> None:
        record = run_process(
            [
                PYTHON,
                "-c",
                "import sys; sys.stderr.write('secret-log\\n'); raise SystemExit(3)",
            ],
            heartbeat_interval=2,
            job_id="failjob1",
        )
        self.assertEqual(record.exit_code, 3)
        self.assertIn("secret-log", record.stderr)
        failed = record.events[-1]
        self.assertEqual(failed["event"], "failed")
        self.assertTrue(failed["is_failure"])
        self.assertEqual(failed["exit_code"], 3)
        self.assertNotIn("secret-log", json.dumps(failed))
        validate_message(failed)

    def test_exit_zero_with_stderr_is_still_completed(self) -> None:
        record = run_process(
            [PYTHON, "-c", "import sys; sys.stderr.write('note\\n')"],
            heartbeat_interval=2,
            job_id="stderr0",
        )
        self.assertEqual(record.events[-1]["event"], "completed")
        self.assertIn("note", record.stderr)

    def test_explicit_percent_becomes_progress(self) -> None:
        record = run_process(
            [
                PYTHON,
                "-u",
                "-c",
                "print('working 40%', flush=True)\n"
                "import time; time.sleep(0.05)\n"
                "print('working 90%', flush=True)\n",
            ],
            heartbeat_interval=5,
            job_id="percent1",
        )
        progress = [event["progress"] for event in record.events if event["event"] == "progress"]
        self.assertEqual(progress, [40, 90])
        self.assertLess(
            names(record.events).index("progress"),
            names(record.events).index("completed"),
        )

    def test_missing_program_fails_without_a_shell(self) -> None:
        record = run_process(["echo hello"], heartbeat_interval=0.2, job_id="noshell1")
        self.assertIsNone(record.pid)
        self.assertEqual(record.exit_code, 127)
        self.assertEqual(names(record.events), ["failed"])
        self.assertEqual(record.events[0]["message"], "Could not start the command")

    def test_a_shell_string_is_refused(self) -> None:
        with self.assertRaises(TypeError):
            run_process("echo hi")  # type: ignore[arg-type]


class CommandLineTests(unittest.TestCase):
    def test_local_command_prints_events_and_keeps_output_off_stdout(self) -> None:
        completed = subprocess.run(
            [
                PYTHON,
                str(ROOT / "mac-agent" / "run_job.py"),
                "--heartbeat",
                "0.1",
                "--job-id",
                "clijob01",
                "--",
                PYTHON,
                "-c",
                "import time; time.sleep(0.2); print('hidden-out')",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        events = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(events[0]["event"], "started")
        self.assertEqual(events[-1]["event"], "completed")
        self.assertNotIn("hidden-out", completed.stdout)
        self.assertIn("pid=", completed.stderr)
        self.assertIn("exit_code=0", completed.stderr)
        self.assertNotIn("STILL_LOADING_TOKEN", completed.stderr)

    def test_command_after_double_dash(self) -> None:
        self.assertEqual(command_argv(["--", "python3", "-c", "print(1)"]), ["python3", "-c", "print(1)"])

    def test_missing_command_does_not_start_a_process(self) -> None:
        self.assertEqual(main([]), 2)
