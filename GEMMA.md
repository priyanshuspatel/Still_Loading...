# Gemma failure analysis

Gemma reads a redacted failure log on the Mac and returns a JSON diagnosis. The monitor keeps running when Gemma is off, slow, or wrong. The Arduino UNO Q does not run the model.

## Why the evidence is shown

Gemma's explanation is not trusted merely because the model said it. The web UI shows the cited log line next to the diagnosis, and Python checks that the citation is actually in the log that was sent. A fluent explanation with a made-up line is marked `unverified`. That is what "open" is for here: the supporting log stays visible, so a hallucinated cause is easier to see than if the raw line were hidden behind a summary.

## What runs where

| Step | Where |
| --- | --- |
| Job runner, heartbeat watchdog, log capture | Mac |
| Secret redaction and evidence check | Mac (`shared/gemma_analysis.py`) |
| Gemma HTTP call | Mac, OpenAI-compatible endpoint (default `http://127.0.0.1:11434/v1`, model `gemma2:2b`) |
| Light matrix, battery, download, job progress | UNO Q, unchanged codes |

`shared/model_feasibility.py` still marks the QRB2210 as `gemma_placement=disabled_on_board`. A 2 GB or 4 GB board sharing RAM with Linux, Docker, and Wi-Fi is the wrong place for this model. The earlier hardware note stands: an on-board small model risks an out-of-memory kill and thermal throttling. The board keeps the rules explainer if it has to explain a failure locally, and it keeps the existing LED states.

## Enable it

```bash
cd ~/still-loading/mac-agent
GEMMA_ENABLED=1 \
GEMMA_BASE_URL=http://127.0.0.1:11434/v1 \
GEMMA_MODEL=gemma2:2b \
python3 run_job.py --gemma -- python3 -c "import non_existent_pkg_xyz"
```

`GEMMA_API_KEY` is optional and is read from the environment. Do not put a real key in the repo. `GEMMA_ENABLED` defaults to off so the existing rules path stays the one used by tests and by an unconfigured agent.

Rebuild the evidence baseline from live commands (this does not invent log lines):

```bash
python3 scripts/capture_failure_baseline.py
```

The fixture is `shared/fixtures/failure_baseline.json`. The local history database had failed jobs but empty excerpts, so those rows are noted and are not used as log evidence.

## What the code accepts

Gemma must return:

```json
{
  "diagnosis": "...",
  "confidence": 0.0,
  "evidence": [{ "log_line": "...", "reason": "..." }],
  "recommended_action": "...",
  "severity": "info|warning|error|critical"
}
```

Every `log_line` has to appear, in order, inside the redacted log. Whitespace can collapse. A citation shorter than 8 characters is rejected. If any citation is missing, the status is `unverified` and the bad line is still shown. The code does not drop it and then mark the rest verified.

Timeouts, connection failures, and JSON that does not match the schema use the rules explainer, set `source` to `fallback`, and do not use the verified status. The watchdog records the stall or failure first, then waits at most `GEMMA_TIMEOUT_SECONDS` (default 8). A stuck model does not block the next heartbeat.

Before the prompt is built, logs pass through `excerpt.redact` and extra patterns for `sk-` keys, AWS-style access key ids, `x-api-key` headers, and URL userinfo. The client logs status and length, not the prompt.

## Limits

- **Latency.** One Mac-side call to local `gemma2:2b` through Ollama on this development machine returned a verified citation in about 4.6 seconds. A cold start can be slower than the 8 second budget. The failed event then carries the rules fallback instead of a model diagnosis. Raising the timeout delays the `failed` wire event by that same budget, because the protocol cannot attach a later explanation after `failed`. That timing was not measured on the UNO Q.
- **Availability.** If Ollama is not running, or `GEMMA_ENABLED` is unset, nothing is sent to a model. Status is the rules explanation, or `unavailable` when a call was attempted and failed.
- **Malformed output.** Models still wrap JSON in prose. Fenced JSON is parsed. Anything that is not the required object is `malformed`.
- **Network.** The client retries only inside the one timeout budget (`GEMMA_MAX_RETRIES`, default 1). It does not retry forever.
- **Watchdog.** `suspected_stall` is still "no heartbeat for 6 seconds." It is not a job failure. Gemma may comment on the captured log after the stall is already on the lights. If there is no log yet, the analysis is the empty-log fallback.
- **Context.** Logs are cut to `GEMMA_MAX_LOG_CHARS` (default 6000) after redaction. A citation has to be in the text that was actually sent. The wire excerpt remains 512 characters. The Mac-side watchdog can use the longer remembered log.
- **Evidence check.** The check is a contiguous substring match. It proves the quote is in the log. It does not prove the diagnosis is the right cause, that the reason sentence is fair, or that a shorter true fragment was the best line to cite.
- **Secrets.** Redaction is pattern-based. A novel secret shape can still be in the prompt. Do not point Gemma at raw config files.
- **UNO Q.** The matrix does not render the diagnosis. Battery percent, charging, Chrome download percent, job progress, completed, failed, and stall keep their existing frames and priority. A Gemma object on the job event does not change those codes.

## Hardware status

Software tests cover the analysis, the watchdog, redaction, the UI card model, and the existing light states. They do not flash the physical matrix. See the Gemma section in `HARDWARE_VERIFICATION.md`. Do not treat a passing unit test as a board test.
