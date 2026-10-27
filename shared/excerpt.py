"""Extract and sanitize short failure log excerpts from captured output.

Phase 6 keeps the full stdout/stderr on the Mac and sends only a short,
redacted trailing excerpt inside the ``failed`` event.  The excerpt is
capped at ``MAX_EXCERPT_BYTES`` (default 512) and ``MAX_EXCERPT_LINES``
(default 10) so it fits comfortably in the 8192-byte wire message.

Secret redaction is applied before the excerpt is attached to the event.
"""

from __future__ import annotations

import re

MAX_EXCERPT_BYTES = 512
MAX_EXCERPT_LINES = 10

# Patterns that should be redacted from the excerpt before it goes on the wire.
# Each entry is (compiled regex, replacement string).
_REDACT_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Bearer token values — match the header line or environment variable style
    (re.compile(r"(Bearer\s+)\S+", re.IGNORECASE), r"\1[REDACTED]"),
    # Authorization header values
    (re.compile(r"(Authorization:\s*)\S+", re.IGNORECASE), r"\1[REDACTED]"),
    # Generic token/secret/password/key assignments: KEY=value, KEY="value", KEY='value'
    (re.compile(
        r"((?:TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|APIKEY|PRIVATE_KEY|ACCESS_KEY"
        r"|AUTH|CREDENTIAL)[_A-Z0-9]*\s*[=:]\s*)['\"]?[^\s'\"]+['\"]?",
        re.IGNORECASE,
    ), r"\1[REDACTED]"),
    # Hex strings that look like tokens (32+ hex chars in a row)
    (re.compile(r"\b[0-9a-fA-F]{32,}\b"), "[REDACTED_HEX]"),
]


def redact(text: str) -> str:
    """Remove likely secrets from a string."""
    result = text
    for pattern, replacement in _REDACT_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def _tail_lines(text: str, max_lines: int, max_bytes: int) -> str:
    """Return the last ``max_lines`` lines within ``max_bytes``."""
    if not text:
        return ""
    lines = text.splitlines(keepends=True)
    selected: list[str] = []
    remaining = max_bytes
    for line in reversed(lines):
        encoded_len = len(line.encode("utf-8", errors="replace"))
        if encoded_len > remaining and selected:
            break
        selected.append(line)
        remaining -= encoded_len
        if len(selected) >= max_lines:
            break
    selected.reverse()
    return "".join(selected)


def extract_excerpt(
    stdout: str,
    stderr: str,
    *,
    max_lines: int = MAX_EXCERPT_LINES,
    max_bytes: int = MAX_EXCERPT_BYTES,
) -> str:
    """Build a redacted trailing excerpt, preferring stderr over stdout.

    Stderr usually contains the actual error message (tracebacks, compiler
    errors, permission denials).  When stderr is empty or whitespace-only,
    the excerpt falls back to stdout.  When both are empty the excerpt is
    an empty string and should not be attached to the wire event.
    """
    # Prefer stderr; fall back to stdout
    source = stderr.rstrip() if stderr.strip() else stdout.rstrip()
    if not source.strip():
        return ""
    tail = _tail_lines(source, max_lines, max_bytes)
    return redact(tail).rstrip()


def safe_excerpt_for_event(
    stdout: str,
    stderr: str,
    *,
    max_lines: int = MAX_EXCERPT_LINES,
    max_bytes: int = MAX_EXCERPT_BYTES,
) -> str | None:
    """Return the excerpt string, or ``None`` when there is nothing useful.

    Callers should attach the result to the ``failed`` event only when the
    return value is not ``None``.
    """
    text = extract_excerpt(stdout, stderr, max_lines=max_lines, max_bytes=max_bytes)
    return text if text else None
