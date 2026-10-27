"""OpenAI-compatible client for a local or remote Gemma endpoint.

Still Loading talks to Gemma from the Mac. The UNO Q receiver does not import
this module. The default endpoint is the local Ollama server
(``http://127.0.0.1:11434/v1``) with ``gemma2:2b``, which is the model already
present on the development machine. Override the URL, model, and key with
environment variables. The API key is never written into source or logs.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, replace

logger = logging.getLogger("still_loading.gemma")


class GemmaError(Exception):
    """Base error for the Gemma client."""


class GemmaTimeout(GemmaError):
    """The endpoint did not answer inside the configured budget."""


class GemmaUnavailable(GemmaError):
    """The endpoint could not be reached or refused the request."""


@dataclass(frozen=True)
class GemmaConfig:
    enabled: bool
    base_url: str
    model: str
    api_key: str
    timeout_s: float
    max_retries: int
    max_log_chars: int

    @classmethod
    def from_env(cls) -> "GemmaConfig":
        enabled_raw = os.environ.get("GEMMA_ENABLED", "0").strip().lower()
        try:
            timeout_s = float(os.environ.get("GEMMA_TIMEOUT_SECONDS", "8"))
        except ValueError:
            timeout_s = 8.0
        try:
            retries = int(os.environ.get("GEMMA_MAX_RETRIES", "1"))
        except ValueError:
            retries = 1
        try:
            max_log = int(os.environ.get("GEMMA_MAX_LOG_CHARS", "6000"))
        except ValueError:
            max_log = 6000
        return cls(
            enabled=enabled_raw in {"1", "true", "yes", "on"},
            base_url=os.environ.get("GEMMA_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/"),
            model=os.environ.get("GEMMA_MODEL", "gemma2:2b"),
            api_key=os.environ.get("GEMMA_API_KEY", ""),
            timeout_s=max(0.2, timeout_s),
            max_retries=max(0, retries),
            max_log_chars=max(200, max_log),
        )


def endpoint_answers(base_url: str, timeout_s: float = 1.5) -> bool:
    """True when the OpenAI-compatible server accepts a connection.

    An HTTP error still counts: the process is up. A connection failure does not.
    """
    url = base_url.rstrip("/") + "/models"
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            response.read()
        return True
    except urllib.error.HTTPError:
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def resolve_control_gemma_config() -> GemmaConfig:
    """Config for the Control Deck.

    An explicit ``GEMMA_ENABLED`` value wins. When the variable is unset, a
    reachable local endpoint is used with the existing default URL and model.
    """
    cfg = GemmaConfig.from_env()
    if os.environ.get("GEMMA_ENABLED") is not None:
        return cfg
    if endpoint_answers(cfg.base_url):
        logger.info(
            "gemma control deck using reachable endpoint model=%s url=%s",
            cfg.model,
            cfg.base_url,
        )
        return replace(cfg, enabled=True)
    return cfg


class GemmaClient:
    """Chat-completions client with one total time budget across retries."""

    def __init__(
        self,
        config: GemmaConfig | None = None,
        *,
        transport=None,
    ) -> None:
        self.config = config or GemmaConfig.from_env()
        # transport(payload, timeout_s) -> model text. Tests inject this.
        self._transport = transport

    def complete(self, prompt: str) -> str:
        payload = {
            "model": self.config.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You analyze one failed software log. Reply with a single JSON object "
                        "and no markdown. Keys: diagnosis (string), confidence (number from 0 to 1), "
                        "evidence (array of objects with log_line and reason), recommended_action (string), "
                        "severity (info, warning, error, or critical). "
                        "Every log_line must be copied from the user log. Do not invent log lines."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        deadline = time.monotonic() + self.config.timeout_s
        attempts = self.config.max_retries + 1
        last_error: GemmaError | None = None
        for attempt in range(attempts):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise GemmaTimeout(
                    f"Gemma budget of {self.config.timeout_s:.1f}s exhausted"
                )
            try:
                if self._transport is not None:
                    text = self._transport(payload, remaining)
                else:
                    text = self._post(payload, remaining)
                if not isinstance(text, str) or not text.strip():
                    raise GemmaUnavailable("Gemma returned an empty body")
                logger.info(
                    "gemma complete ok model=%s attempt=%s chars=%s",
                    self.config.model,
                    attempt + 1,
                    len(text),
                )
                return text
            except GemmaTimeout as exc:
                last_error = exc
                logger.warning(
                    "gemma timeout model=%s attempt=%s",
                    self.config.model,
                    attempt + 1,
                )
            except GemmaUnavailable as exc:
                last_error = exc
                logger.warning(
                    "gemma unavailable model=%s attempt=%s error=%s",
                    self.config.model,
                    attempt + 1,
                    exc,
                )
            if attempt + 1 >= attempts:
                break
        if isinstance(last_error, GemmaTimeout):
            raise last_error
        raise last_error or GemmaUnavailable("Gemma request failed")

    def _post(self, payload: dict, timeout_s: float) -> str:
        url = f"{self.config.base_url}/chat/completions"
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except TimeoutError as exc:
            raise GemmaTimeout("Gemma request timed out") from exc
        except urllib.error.HTTPError as exc:
            # Do not log the body: an error page can echo the prompt.
            logger.warning("gemma http status=%s", exc.code)
            if exc.code in {408, 429, 500, 502, 503, 504}:
                raise GemmaUnavailable(f"Gemma HTTP {exc.code}") from exc
            raise GemmaUnavailable(f"Gemma HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, TimeoutError):
                raise GemmaTimeout("Gemma request timed out") from exc
            raise GemmaUnavailable("Gemma endpoint unreachable") from exc
        return _message_text(raw)


def _message_text(raw: str) -> str:
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(body, dict):
        choices = body.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
        if isinstance(body.get("response"), str):
            return body["response"]
    return raw
