"""Rules-based failure explanation for Still Loading...

Phase 7: Generates concise, structured failure explanations from exit codes,
error messages, and sanitized failure log excerpts.

Zero-overhead rules-first implementation:
- 0 ms latency, no external dependencies (stdlib only)
- Deterministic and safe for low-resource environments (Qualcomm QRB2210 / 2GB RAM)
- Provides category, human-readable summary, actionable suggestion, and confidence score.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class FailureExplanation:
    category: str
    summary: str
    suggestion: str
    confidence: float
    source: str = "rules"

    def to_dict(self) -> dict:
        return asdict(self)


# -------------------------------------------------------------------------
# Known Signal & Exit Code Definitions (POSIX / macOS / Linux)
# -------------------------------------------------------------------------

_SIGNAL_EXPLANATIONS: dict[int, tuple[str, str, str]] = {
    126: (
        "permission_denied",
        "Command cannot execute: permission denied or not executable",
        "Check execute permissions with 'chmod +x <file>' or verify file accessibility.",
    ),
    127: (
        "command_not_found",
        "Command not found",
        "Verify the program name spelling and that its executable directory is in $PATH.",
    ),
    130: (
        "interrupted",
        "Process was interrupted by user (SIGINT / Ctrl-C)",
        "The operation was aborted before completion. Rerun the command to restart.",
    ),
    137: (
        "out_of_memory",
        "Process was forcefully killed (SIGKILL / Out of Memory)",
        "The operating system or container killed the process, likely due to memory limits.",
    ),
    139: (
        "segmentation_fault",
        "Segmentation fault (SIGSEGV)",
        "A low-level crash occurred due to invalid memory access or null pointer dereference.",
    ),
    143: (
        "terminated",
        "Process received termination signal (SIGTERM)",
        "The process was gracefully asked to shut down by an external process or daemon.",
    ),
}


# -------------------------------------------------------------------------
# Pattern Rules for Log Excerpts
# -------------------------------------------------------------------------

# Each rule is a tuple: (compiled_regex, category, summary_fn, suggestion_fn)
# summary_fn and suggestion_fn receive the re.Match object.

def _rule_missing_py_module(m: re.Match) -> tuple[str, str, str]:
    mod = m.group(1).split(".")[0]
    return (
        "missing_dependency",
        f"Missing Python module: '{mod}'",
        f"Install it with 'pip install {mod}' or add '{mod}' to your project dependencies.",
    )


def _rule_missing_node_module(m: re.Match) -> tuple[str, str, str]:
    mod = m.group(1).strip()
    return (
        "missing_dependency",
        f"Missing Node.js module: '{mod}'",
        f"Install it with 'npm install {mod}' or 'yarn add {mod}'.",
    )


def _rule_py_syntax_error(m: re.Match) -> tuple[str, str, str]:
    detail = m.group(1).strip() if m.group(1) else "Syntax error"
    return (
        "syntax_error",
        f"Python syntax error: {detail}",
        "Review the file and line indicated in the traceback for syntax mistakes or unclosed brackets.",
    )


def _rule_file_not_found(m: re.Match) -> tuple[str, str, str]:
    path = m.group(1).strip()
    return (
        "file_not_found",
        f"File or directory not found: '{path}'",
        f"Verify that '{path}' exists and that the working directory is correct.",
    )


def _rule_permission_denied(m: re.Match) -> tuple[str, str, str]:
    target = m.group(1).strip() if m.group(1) else "file or resource"
    return (
        "permission_denied",
        f"Permission denied: {target}",
        "Verify read/write permissions or run with the required user privileges.",
    )


def _rule_out_of_memory(m: re.Match) -> tuple[str, str, str]:
    return (
        "out_of_memory",
        "Process ran out of memory (MemoryError)",
        "Reduce memory usage, decrease batch sizes, or increase system swap/memory limits.",
    )


def _rule_zero_division(m: re.Match) -> tuple[str, str, str]:
    return (
        "runtime_error",
        "Division by zero error",
        "Check denominator values and add guards against zero before dividing.",
    )


def _rule_type_value_error(m: re.Match) -> tuple[str, str, str]:
    err_type = m.group(1)
    msg = m.group(2).strip()
    return (
        "runtime_error",
        f"{err_type}: {msg}",
        "Inspect function arguments and variable types leading up to the failure.",
    )


def _rule_test_failure(m: re.Match) -> tuple[str, str, str]:
    return (
        "test_failure",
        "Automated test suite failed assertions",
        "Inspect the failing test cases in the test runner output and verify expected values.",
    )


def _rule_rust_compiler(m: re.Match) -> tuple[str, str, str]:
    code = m.group(1)
    msg = m.group(2).strip()
    return (
        "compiler_error",
        f"Rust compiler error [{code}]: {msg}",
        f"Run 'rustc --explain {code}' for detailed fix instructions.",
    )


def _rule_c_missing_header(m: re.Match) -> tuple[str, str, str]:
    hdr = m.group(1).strip()
    return (
        "missing_dependency",
        f"Missing C/C++ header: <{hdr}>",
        f"Install development libraries for '{hdr}' (e.g. via brew or apt).",
    )


def _rule_c_undefined_ref(m: re.Match) -> tuple[str, str, str]:
    sym = m.group(1).strip()
    return (
        "linker_error",
        f"Undefined symbol / reference: '{sym}'",
        f"Check that the library defining '{sym}' is linked (-l) or source file compiled.",
    )


def _rule_network_connection(m: re.Match) -> tuple[str, str, str]:
    code = m.group(1) if m.group(1) else "Connection failed"
    return (
        "network_error",
        f"Network connection error ({code})",
        "Check internet connection, DNS resolution, and target server availability.",
    )


def _rule_git_conflict(m: re.Match) -> tuple[str, str, str]:
    file_path = m.group(1).strip() if m.group(1) else ""
    target = f" in '{file_path}'" if file_path else ""
    return (
        "merge_conflict",
        f"Git merge conflict{target}",
        "Resolve merge conflicts in marked files, stage them with 'git add', and commit.",
    )


def _rule_git_not_repo(m: re.Match) -> tuple[str, str, str]:
    return (
        "git_error",
        "Not a git repository",
        "Run 'git init' or change directory to a valid git repository.",
    )


def _rule_docker_daemon(m: re.Match) -> tuple[str, str, str]:
    return (
        "docker_error",
        "Cannot connect to the Docker daemon",
        "Ensure Docker Desktop or the dockerd service is running and accessible.",
    )


_EXCERPT_PATTERNS: list[tuple[re.Pattern, callable]] = [
    # Python missing module
    (re.compile(r"ModuleNotFoundError:\s+No module named ['\"]([^'\"]+)['\"]", re.IGNORECASE), _rule_missing_py_module),
    (re.compile(r"ImportError:\s+cannot import name ['\"]?[^'\"]+['\"]?\s+from\s+['\"]([^'\"]+)['\"]", re.IGNORECASE), _rule_missing_py_module),
    (re.compile(r"ImportError:\s+No module named ['\"]([^'\"]+)['\"]", re.IGNORECASE), _rule_missing_py_module),

    # Node.js missing module
    (re.compile(r"Error:\s+Cannot find module ['\"]([^'\"]+)['\"]", re.IGNORECASE), _rule_missing_node_module),
    (re.compile(r"MODULE_NOT_FOUND.*['\"]([^'\"]+)['\"]", re.IGNORECASE), _rule_missing_node_module),

    # Python syntax / indentation error
    (re.compile(r"IndentationError:\s+(.+)", re.IGNORECASE), _rule_py_syntax_error),
    (re.compile(r"SyntaxError:\s+(.+)", re.IGNORECASE), _rule_py_syntax_error),

    # File not found
    (re.compile(r"FileNotFoundError:\s+\[Errno 2\]\s+No such file or directory:\s+['\"]?([^'\"\n]+)['\"]?", re.IGNORECASE), _rule_file_not_found),
    (re.compile(r"No such file or directory:\s+['\"]?([^'\"\n]+)['\"]?", re.IGNORECASE), _rule_file_not_found),
    (re.compile(r"ENOENT:\s+no such file or directory.*['\"]([^'\"]+)['\"]", re.IGNORECASE), _rule_file_not_found),

    # Permission denied
    (re.compile(r"PermissionError:\s+\[Errno 13\]\s+Permission denied:\s+['\"]?([^'\"\n]+)['\"]?", re.IGNORECASE), _rule_permission_denied),
    (re.compile(r"EACCES:\s+permission denied.*['\"]?([^'\"\n]+)['\"]?", re.IGNORECASE), _rule_permission_denied),

    # Out of memory
    (re.compile(r"\bMemoryError\b", re.IGNORECASE), _rule_out_of_memory),
    (re.compile(r"JavaScript heap out of memory", re.IGNORECASE), _rule_out_of_memory),
    (re.compile(r"fatal error:\s+runtime:\s+out of memory", re.IGNORECASE), _rule_out_of_memory),

    # Math / runtime
    (re.compile(r"\bZeroDivisionError:\s*(.*)", re.IGNORECASE), _rule_zero_division),
    (re.compile(r"\b(TypeError|ValueError|AttributeError|KeyError|IndexError):\s*(.+)", re.IGNORECASE), _rule_type_value_error),

    # Tests
    (re.compile(r"\bFAILED\s+\(failures=\d+", re.IGNORECASE), _rule_test_failure),
    (re.compile(r"\bFAIL:\s+\S+\s+\(", re.IGNORECASE), _rule_test_failure),
    (re.compile(r"\bAssertionError\b", re.IGNORECASE), _rule_test_failure),
    (re.compile(r"\b\d+\s+failed,\s+\d+\s+passed\b", re.IGNORECASE), _rule_test_failure),

    # Rust
    (re.compile(r"error\[(E\d+)\]:\s+(.+)", re.IGNORECASE), _rule_rust_compiler),

    # C / C++
    (re.compile(r"fatal error:\s+([^:\n]+):\s+No such file or directory", re.IGNORECASE), _rule_c_missing_header),
    (re.compile(r"undefined reference to `([^']+)'", re.IGNORECASE), _rule_c_undefined_ref),

    # Network
    (re.compile(r"\b(ECONNREFUSED|ENOTFOUND|ETIMEDOUT|ConnectionRefusedError)\b", re.IGNORECASE), _rule_network_connection),

    # Git
    (re.compile(r"CONFLICT\s+\(content\):\s+Merge conflict in\s+([^\n]+)", re.IGNORECASE), _rule_git_conflict),
    (re.compile(r"fatal:\s+not a git repository", re.IGNORECASE), _rule_git_not_repo),

    # Docker
    (re.compile(r"Cannot connect to the Docker daemon", re.IGNORECASE), _rule_docker_daemon),
]


# -------------------------------------------------------------------------
# Main Explanation Function
# -------------------------------------------------------------------------

def explain_failure(
    exit_code: int = 1,
    message: str = "",
    excerpt: str | None = None,
) -> FailureExplanation:
    """Analyze an exit code, failure message, and log excerpt to explain a failure.

    Returns a ``FailureExplanation`` with category, summary, actionable suggestion,
    and confidence score (1.0 for specific log match, 0.7 for signal code, 0.4 for generic).
    """
    text_to_scan = f"{excerpt or ''}\n{message or ''}".strip()

    # 1. First, check log excerpt for specific error patterns (highest confidence: 1.0)
    if text_to_scan:
        for pattern, rule_fn in _EXCERPT_PATTERNS:
            match = pattern.search(text_to_scan)
            if match:
                category, summary, suggestion = rule_fn(match)
                return FailureExplanation(
                    category=category,
                    summary=summary,
                    suggestion=suggestion,
                    confidence=1.0,
                    source="rules",
                )

    # 2. Check exit code for known POSIX / OS signals (confidence: 0.7)
    if exit_code in _SIGNAL_EXPLANATIONS:
        cat, sum_text, sug_text = _SIGNAL_EXPLANATIONS[exit_code]
        return FailureExplanation(
            category=cat,
            summary=sum_text,
            suggestion=sug_text,
            confidence=0.7,
            source="rules",
        )

    # 3. Fallback: extract last line of excerpt if available (confidence: 0.5)
    if excerpt and excerpt.strip():
        last_line = excerpt.strip().splitlines()[-1].strip()
        if len(last_line) > 120:
            last_line = last_line[:117] + "..."
        return FailureExplanation(
            category="generic_error",
            summary=f"Error (exit {exit_code}): {last_line}",
            suggestion="Review the trailing error excerpt above to identify and fix the issue.",
            confidence=0.5,
            source="rules",
        )

    # 4. Minimal fallback when no excerpt or signal information is present (confidence: 0.3)
    clean_msg = message.strip() if message else f"Process exited with code {exit_code}"
    return FailureExplanation(
        category="generic_error",
        summary=clean_msg,
        suggestion="Run the command manually with verbose output to inspect stderr.",
        confidence=0.3,
        source="rules",
    )
