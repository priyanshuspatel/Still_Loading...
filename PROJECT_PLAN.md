# Still Loading... project plan

Tagline: Stop staring. Start living.

This plan records what is already in the repository, the architecture we will build toward, and the phase boundaries. Phases 1 and 2 are implemented. The Phase 2 receiver has been verified on the Mac only.

## What exists today

The workspace is `/Users/priyanshuswapneshpatel/still-loading` on branch `main`. Before this phase it contained:

- `LICENSE` (MIT, copyright 2026 Priyanshu Patel)
- `mac-agent/job_agent.py`, a single-file simulator with modes `normal`, `slow`, `hang`, and `fail`
- an empty `docs/` directory
- a local `.venv` with Python 3.13.17 and pip, and no project packages

The old simulator already printed JSON for start, heartbeat, progress, failure, and completion. It slept in real time, used a random job id, and had no tests. Heartbeats already stopped in `hang` while the process kept running, which is the right idea.

Python on this Mac: 3.13.17 at `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3`.

## Architecture

Four pieces stay separate so each one can be tested on its own.

1. **Mac agent** (`mac-agent/`). Watches a job and emits events. Phase 1 only simulates jobs.
2. **Local messages.** The Mac POSTs one JSON event to `POST /v1/events` on port 8090. The receiver is Python's standard-library HTTP server, so the same file runs on macOS and on the UNO Q's Debian userland. A bearer token in `config.local.json` or `STILL_LOADING_TOKEN` guards event writes and job read-back. `GET /health` returns no job data. Bridge stays the on-board Linux-to-microcontroller link and is not the Mac-to-board path. No cloud service.
3. **UNO Q Linux app.** Official path is an Arduino App Lab app: Python on the Qualcomm QRB2210 (Debian) receives messages, keeps job state, and calls the microcontroller. Deploy with the App Lab **Run** button over a USB-C data cable, or from App Lab running on the board. First Linux boot takes about 20–30 seconds, and the LED matrix shows a boot animation during that time.
4. **UNO Q microcontroller sketch.** The STM32U585 owns the 8×13 blue LED matrix (`Arduino_LED_Matrix`) and two active-low RGB LEDs (LED 3 on PH10–PH12 and LED 4 on PH13–PH15). The Linux side calls those functions through Bridge (`Bridge.provide` in the sketch, `Bridge.call` from Python). Two more RGB LEDs are wired to the Linux processor; LED 2 is a system-status light by default, so the product animations should use the microcontroller LEDs and the matrix.

State names for a later engine, kept out of the simulator on purpose: `IDLE`, `STARTING`, `RUNNING`, `SLOW`, `SUSPECTED_STALL`, `FAILED`, `COMPLETED`. A missing heartbeat becomes `SUSPECTED_STALL`. An explicit `failed` event becomes `FAILED`. AI does not make that decision.

The board has Wi-Fi 5 and either 2 GB or 4 GB of RAM, depending on the variant. This plan does not assume which variant is on the desk, and it does not assume a large language model will fit. Phase 7 starts with a small local rules explainer unless a measured model is shown to fit.

Sources checked on 24 October 2026:

- [UNO Q hardware](https://docs.arduino.cc/hardware/uno-q)
- [UNO Q user manual](https://docs.arduino.cc/tutorials/uno-q/user-manual/)
- [Router Bridge tutorial](https://docs.arduino.cc/tutorials/uno-q/routerbridge-multilanguage/)
- [UNO Q datasheet](https://docs.arduino.cc/resources/datasheets/ABX00162-datasheet.pdf)

## File layout

```text
still-loading/
├── README.md
├── PROJECT_PLAN.md
├── LICENSE
├── .gitignore
├── mac-agent/
│   ├── job_agent.py          simulator command
│   ├── simulator.py          scenarios and the local event clock
│   ├── sender.py             HTTP client
│   ├── send_events.py        send a scenario or one probe
│   ├── runner.py             local process capture and events
│   ├── run_job.py            command line for one real Mac command
│   ├── battery.py            pmset battery parser, deduplication, refresh, and backoff
│   ├── battery_monitor.py    continuous CLI for MacBook battery updates and display mode
│   ├── download_monitor.py   Chrome download progress detector and reporter
│   ├── config.example.json   host, port, and token placeholders
│   └── tests/
├── shared/
│   ├── message_schema.json
│   ├── messages.py           validation and per-job sequence log
│   ├── http_api.py           receiver implementation
│   ├── state_engine.py       light state and job/battery display priority
│   ├── matrix_display.py     8×13 pixel font, frames, and animation timeline
│   └── lights.py             print, status file, optional Bridge call
└── uno-q/
    ├── README.md
    ├── receiver.py           start the receiver on the board or the Mac
    ├── app_lab_main.py       paste into the App Lab Python tab
    └── sketch/sketch.ino     paste into the App Lab Sketch tab
```

## Assumptions

- The Mac and the UNO Q need the same Wi-Fi network before a real probe. The address comes from App Lab or the board's `name.local` hostname, and it is not hardcoded.
- Phase 1 job ids are 8 hex characters unless `--job-id` is passed.
- Scenario timings are fixed: 20 second runs, heartbeats every 2 seconds, progress every 3 seconds (every 8 seconds in `slow`), heartbeats pause at 8 seconds in `hang`, and `fail` fires at 10 seconds.
- `heartbeat_paused` and `scenario_ended` stay on the Mac. The sender skips them. The receiver rejects them as unknown event types. Silence on the wire is the missing-heartbeat signal. The board does not treat a lost HTTP connection as `failed`.

## Risks

- Generic Arduino Uno instructions do not apply to this board. Apps are built in Arduino App Lab, and Linux talks to the microcontroller through Bridge.
- Touching the LED matrix during the 20–30 second boot can interfere with the microcontroller. Wait until the boot animation finishes.
- A lost network connection must not be stored as a job failure. The Phase 1 `hang` scenario is the rehearsal for that rule.
- RAM variant is unknown. Local model choice stays closed until the board is identified.
- No firmware will be wiped or reflashed outside App Lab's normal Run flow unless you approve it.

## Phases

| Phase | Goal | State |
| --- | --- | --- |
| 0 | Audit the repo, check the UNO Q docs, write this plan | Done in this session |
| 1 | Reliable local simulator and tests | Done in this session. See README for the commands and results. |
| 2 | Message schema, validation, Mac sender, and Linux-side receiver | You confirmed a probe to 192.168.1.5:8090. The protocol was left unchanged in Phase 3. |
| 3 | State engine plus the first LED 3 and matrix sketch | Mac tests done in this session. Verified on the board in Phase 4. |
| 4 | Confirm Bridge on the real board and adjust the sketch only if a light test fails | Verified on real UNO Q hardware (HTTP `/v1/lights` -> App Lab `Bridge.call` -> LED 3 + 8×13 matrix). |
| 4.1 | Watch one real Mac command and emit the existing job events | Verified on Mac and on real UNO Q hardware with `run_job.py --send`. |
| 5 | Matrix and RGB polish, live `%` display, continuous MacBook battery indicator, and Chrome download monitor | Implemented and verified by 74 Mac tests. Ready for manual App Lab hardware check. |
| 6 | Short log excerpts on failure, still without an AI explanation | Implemented with secret redaction and verified by 106 Mac tests. |
| 7 | Failure explanations. Rules first. A model only after a feasibility check. | Implemented with zero-overhead rules explainer + hardware feasibility benchmark. Verified by 138 Mac tests. |
| 8 | Demo script and a list of what was verified on the hardware | Implemented interactive demo script (`mac-agent/demo.py`) and documented full hardware verification (`HARDWARE_VERIFICATION.md`). |
| 9 | End-to-end failure intelligence surfaced in the web dashboard | Implemented Failure Intelligence Card in `web/src/components/LiveDashboard.tsx`. Verified: 4/4 web tests pass, production build succeeds (256 kB JS). |
| 10 | Daemon templates & operational sync scripts | Implemented systemd unit (`uno-q/still-loading-receiver.service`), launchd plists (`mac-agent/launchd/`), sync script (`scripts/sync_to_board.sh`), and hardware verification script (`scripts/verify_hardware.sh`). |
| 11 | Live ANSI Terminal Monitor & ASCII matrix twin | Implemented zero-dependency terminal dashboard (`mac-agent/terminal_monitor.py`) with 8×13 LED matrix twin, battery/download monitors, and failure intelligence. Verified by 5 new unit tests (143 total Mac tests). |
| 12 | Monorepo test runner & GitHub Actions CI | Implemented single-command monorepo runner (`scripts/test_all.sh`) passing 152/152 tests across 5 suites, and multi-OS GitHub Actions workflow (`.github/workflows/ci.yml`). |
| 13 | Persistent Job History & Analytics Store | Implemented lightweight SQLite store (`shared/history_store.py`) recording terminal jobs with duration, status, exit code, failure classification, and excerpts. Exposes `GET /v1/history` and `GET /v1/history/stats`. Verified by 3 new unit tests (146 Mac tests). |
| 14 | Job History & Analytics Web UI + CLI Viewer | Built dedicated `web/src/components/JobHistory.tsx` with KPI metrics cards and expandable failure intelligence, plus `mac-agent/history_cli.py` for terminal history queries. Verified by web tests and production build. |
| 15 | Ambient audio cues (macOS afplay & Web Audio API synthesizer) | Implemented zero-dependency macOS system audio cues (`mac-agent/audio.py`, 14 new tests) and web Web Audio synthesizer (`web/src/lib/audioCues.ts`). Verified by 160 Mac tests + web build. |
| 16 | Native macOS Desktop Notifications | Implemented asynchronous Notification Center banners via `mac-agent/notifications.py` and `--notify` flag on `run_job.py`. Verified by 12 new unit tests (172 Mac tests, 178 total monorepo tests). |

## Phase 1 decisions

- Kept the four existing modes and the original failure message, `Simulated build error`.
- Moved the scenario logic into `simulator.py` so tests can call it without starting the command line.
- Added a manual clock. Tests finish in well under a second. `--fast` uses the same clock with today's time as the start.
- Live runs schedule each tick and record the scenario time, so a real `fail` run reports the same `elapsed_seconds` as the tests. On 24 October 2026 that live run took 10.04 seconds of wall time and reported `elapsed_seconds` 10.0.
- Added `sequence`, UTC timestamps, `schema_version`, `is_failure`, and `exit_code` on terminal outcomes.
- Standard library only. Tests use `unittest`.

## Phase 2 decisions

- Wire schema version stays 1 and reuses the simulator fields for `started`, `heartbeat`, `progress`, `failed`, and `completed`.
- Sequence numbers are the duplicate and stale check. Timestamps are stored and are not the ordering key, because the Mac clock and the board clock can disagree.
- After `failed` or `completed`, a higher sequence is refused. That is a delivery rule. It is not the Phase 3 state machine.
- The board process is `python3 uno-q/receiver.py` over SSH. App Lab Run is left unused so this phase does not flash a sketch.
- On 24 October 2026, `python3 -m unittest discover -s mac-agent/tests -t mac-agent -v` reported 20 tests OK. A loopback probe to `127.0.0.1:8090` was accepted and read back. Later the same day you confirmed a real probe to `192.168.1.5:8090`.

## Phase 3 decisions

- The state engine lives in `shared/state_engine.py` and is called only after `JobLog.accept`. Rejected HTTP messages never reach it. The 202 response body is unchanged.
- Stall timing uses the receiver's monotonic clock. The Mac timestamp inside the JSON is not subtracted from the board clock.
- Default heartbeat timeout is 6 seconds. Default slow-progress gap is 6 seconds. A heartbeat after `suspected_stall` returns the job to `running`.
- Progress can continue during a stall, matching the simulator's `hang` mode, and that progress does not clear the stall and does not set `failed`.
- LED 3 and the matrix are driven by `uno-q/sketch/sketch.ino` through `Bridge.provide("set_job_lights", ...)`, the same provider style as the official `set_led3_color` example. The matrix uses `Arduino_LED_Matrix` with 3-bit grayscale. The matrix is blue, so color is LED 3 only.
- App Lab cannot see the receiver's `/tmp`. The receiver now answers `GET /v1/lights` with the same bearer token. `uno-q/app_lab_main.py` polls that URL, trying the container default gateway, `host.docker.internal`, and `127.0.0.1`, then calls `Bridge.call("set_job_lights", code, progress)`. This path is tested on the Mac and has not been confirmed on the board since the change.
- On 24 October 2026, `python3 -m unittest discover -s mac-agent/tests -t mac-agent -v` reported 30 tests OK in 3.123 seconds. That run did not contact 192.168.1.5.

## Phase 4.1 decisions

- A real command is a list of arguments passed to `subprocess.Popen` with `shell=False`. A single shell string is refused.
- Stdout and stderr are read on separate threads and stored in separate strings. The JSON events do not include either stream, so a captured secret is not sent to the board.
- Exit code 0 is `completed` with progress 100. Any other exit code is `failed`. Text on stderr does not change that. A process with no output still receives heartbeats and is not marked failed.
- `progress` is sent only when a captured line contains an explicit percent, such as `40%`.
- The process id, start time, and captured text stay on the Mac. The board still receives schema version 1 events through the existing sender. `--send` is optional and is not used by the tests.
- You verified Phase 4 and Phase 4.1 on the physical UNO Q with a real Mac process sending `started`, `heartbeat`, `progress`, and `completed` events.

## Phase 5 decisions

- Kept `POST /v1/events`, `GET /v1/jobs/<job_id>`, `GET /v1/lights`, `GET /health`, and `Bridge.provide("set_job_lights", ...)` backward-compatible.
- Added `shared/matrix_display.py` and mirrored its 8×13 bitmaps and timing constants in `uno-q/sketch/sketch.ino`:
  - Job start: two gentle centered heart blinks before entering the running cycle.
  - Running: cycles locally on the MCU between live numeric percentage (`1%`–`99%`, or `100` with a full row-7 bar), three waiting dots (`...`), and an occasional heart pulse.
  - Unknown progress: when no `progress` event has arrived yet (`progress_known` is false / `progress == 0`), the display uses waiting dots and heartbeats and never fabricates `0%`.
  - `100%` compact representation: rendered as three 3×5 digits (`100` across columns 1–11) plus a full 13-pixel bar on row 7 so it fits the 8×13 matrix cleanly.
  - Completed: 3 gentle heart beats, then `100` for 1.8 seconds, then settles into a calm steady checkmark.
  - Failed: steady `X` with corner markers and red LED 3, distinct from all waiting, slow, stall, and completion patterns.
- Added `mac-agent/battery.py` and `mac-agent/battery_monitor.py` using `pmset -g batt` (`shell=False`, no root privileges) and authenticated `POST /v1/battery` + `POST /v1/display-mode`.
  - Reads battery immediately on start and polls continuously every 15 seconds by default (`--interval`), deduplicating unchanged readings while periodically refreshing every 5 minutes (`--refresh-interval 300`) so the board recovers after receiver restarts.
  - Survives temporary receiver outages with exponential backoff (`15s -> 30s -> 60s`), never marks failed deliveries as sent, and sends the latest reading upon reconnection.
- Active Chrome downloads (`download`, code `9`) and active or failed jobs take priority by default (`auto` mode), and battery messages never enter `JobLog` or overwrite job/download state. Explicit `battery` mode uses state codes `6` (`battery`), `7` (`battery_charging`), and `8` (`battery_unavailable` showing `--`).
- Documented the macOS lid-closed sleep limitation and token rotation rules clearly in `README.md`.
- On 25 October 2026, `python3 -m unittest discover -s mac-agent/tests -t mac-agent -v` reported 74 tests OK.

## Phase 6 decisions

- Added `shared/excerpt.py` to extract concise, safe trailing failure excerpts (up to 10 lines and 512 bytes) from captured process output.
- Prioritizes `stderr` over `stdout` (where stack traces and compiler errors usually appear), falling back to `stdout` only if `stderr` is empty.
- Automatically redacts sensitive patterns before sending over the wire: Bearer tokens, Authorization headers, environment variable and password assignments (e.g. `TOKEN=...`, `API_KEY=...`), and long hex strings (>= 32 chars).
- Extended schema version 1 wire format: allowed an optional `excerpt` string field (max 512 characters) exclusively on `failed` events; strictly rejected on all non-failed events (`started`, `heartbeat`, `progress`, `completed`).
- `JobLog.snapshot(job_id)` surfaces `excerpt` at the top level of the snapshot payload in addition to keeping it inside the nested `latest` event dictionary.
- `mac-agent/runner.py` automatically extracts and attaches safe excerpts to `failed` events on non-zero exit codes or termination errors, with an optional `include_excerpt: bool = True` switch.
- `mac-agent/run_job.py` exposes `--no-excerpt` to allow suppressing log excerpts from the wire if desired.
- Added 17 comprehensive unit tests in `mac-agent/tests/test_excerpt.py`. On 26 October 2026, all 106 unit tests passed OK.

## Phase 7 decisions

- Built `shared/explainer.py` implementing a deterministic, zero-overhead rules-first failure explainer:
  - Signals analyzed: exit code 126 (`permission_denied`), 127 (`command_not_found`), 130 (`interrupted`), 137 (`out_of_memory` / killed), 139 (`segmentation_fault`), 143 (`terminated`).
  - Regex pattern matching over log excerpts: Python missing modules (`ModuleNotFoundError`, `ImportError`), syntax/indentation errors, file not found, permission denied, division by zero, type/value errors, test assertions (`FAILED (failures=...)`), Node.js `MODULE_NOT_FOUND`, Rust compiler codes (`error[E0...]`), C/C++ missing headers and undefined references, network errors (`ECONNREFUSED`), git merge conflicts, and Docker daemon errors.
  - Returns structured `FailureExplanation` (`category`, `summary`, `suggestion`, `confidence`, `source="rules"`).
  - Executed in <0.05 ms with zero extra memory allocations and no external dependencies.
- Added `shared/model_feasibility.py` to evaluate local model execution:
  - Assesses host CPU, architecture, and available memory.
  - Formally documents that running an on-device SLM (even 500M quantized) directly on the UNO Q's Qualcomm QRB2210 (2 GB or 4 GB LPDDR4 shared with Debian kernel, Docker container, WiFi, and Bridge) creates severe OOM kill risks (exit 137) and 5–15s thermal throttling on the fanless enclosure.
  - Concludes that the rules-first explainer is the optimal engine for low-resource companion devices, while host Macs with 16+ GB RAM can run local models if desired.
- Wire integration in `shared/messages.py` & `shared/message_schema.json`:
  - Extended `failed` event schema to accept an optional structured `explanation` object (`category`, `summary`, `suggestion`).
  - Strict validation rejects `explanation` on all non-failed events (`completed`, `started`, `heartbeat`, `progress`).
  - `JobLog.snapshot(job_id)` surfaces `explanation` directly, or dynamically generates it via `explain_failure` if missing from older senders.
- `mac-agent/runner.py` and `mac-agent/run_job.py`:
  - Process runner computes and attaches the explanation to `failed` wire events.
  - `run_job.py` formats and prints the human-readable explanation and suggestion to `stderr` upon process failure.
- Added 32 unit tests in `mac-agent/tests/test_explainer.py`. On 26 October 2026, all 138 unit tests passed OK.

## Phase 8 decisions

- Created `mac-agent/demo.py`, a unified demonstration script covering all project scenarios:
  - `normal`: Starting heartbeats, numeric progress, and completion checkmark.
  - `slow`: Delayed progress intervals with continuous heartbeat liveness.
  - `hang`: Heartbeat stall detection, display transition to stall dots, recovery on heartbeat resumption.
  - `fail`: Simulated failure scenario.
  - `process_fail`: Real subprocess execution demonstrating secret redaction, log excerpt capture, and rules-based failure explanation.
  - `battery`: Real macOS `pmset -g batt` battery reading, charging glyphs, and matrix representation.
  - `--fast` mode executes the full suite in under 3 seconds; `--live` provides real-time paced visualization; `--send` posts directly to an active UNO Q receiver.
- Authored [HARDWARE_VERIFICATION.md](file:///Users/priyanshuswapneshpatel/still-loading/HARDWARE_VERIFICATION.md) documenting physical hardware validation on the Arduino UNO Q:
  - Architecture breakdown between Qualcomm QRB2210 Linux userland and STM32U585 microcontroller.
  - Evidence of physical verification: Router Bridge IPC, 8×13 blue LED matrix animations, RGB LED 3 color mapping, battery priority rules, Chrome download percentages, and failure handling.

## Phase 9 decisions

- Added the **Failure Intelligence Card** to `web/src/components/LiveDashboard.tsx` (rendered between the Chrome Download card and the Physical Matrix section).
- The card surfaces conditionally: `currentSnapshot.job?.is_failure || currentMatrixState === 'failed' || currentSnapshot.job?.explanation`.
- Displays: animated AlertTriangle icon, category badge (e.g. `MISSING DEPENDENCY`), exit code badge, job ID, root cause summary, recommended fix command, and a sanitized log excerpt `<pre>` block.
- Copy Fix button uses `navigator.clipboard` and shows a green checkmark for 2 seconds after copy.
- The card uses a red-950 glassmorphism gradient with a subtle ambient glow — visually distinct from all other cards.
- `web/src/types/telemetry.ts`, `web/src/lib/telemetryClient.ts`, and `web/src/lib/demoData.ts` (all updated in Phase 9 predecessor work) provide the typed data surface.
- On 26 October 2026: `npm test` → 4/4 pass; `npm run build` → 256.92 kB JS bundle, 834ms build time, exit 0.

## Phase 10 decisions

- Created `uno-q/still-loading-receiver.service` — a hardened systemd unit for the QRB2210 Debian userland:
  - `After=network-online.target` ensures Wi-Fi is up before the receiver starts.
  - `Restart=on-failure` with `RestartSec=5s` recovers from transient crashes automatically.
  - Process sandboxing via `NoNewPrivileges`, `ProtectSystem=strict`, and `ProtectHome=read-only`.
  - Token is loaded from `/home/arduino/still-loading/.env` or `/etc/still-loading/receiver.env` — never hardcoded.
  - Install: `sudo cp uno-q/still-loading-receiver.service /etc/systemd/system/ && sudo systemctl enable --now still-loading-receiver.service`
- Created `mac-agent/launchd/com.stillloading.battery.plist` — launchd agent for macOS background battery telemetry:
  - `KeepAlive: { SuccessfulExit: false }` keeps the monitor running but allows intentional clean exits.
  - Logs to `/tmp/still-loading-battery.log`.
- Created `mac-agent/launchd/com.stillloading.relay.plist` — launchd agent for running the telemetry relay as a background service on the Mac.
- Created `mac-agent/launchd/README.md` documenting install/unload steps for both launchd agents.
- Created `scripts/sync_to_board.sh` — rsync-based code push script:
  - Syncs `shared/` and `uno-q/` to `arduino@<BOARD_IP>:~/still-loading` over SSH.
  - Falls back to `scp` if rsync is unavailable.
  - `--restart` flag triggers `sudo systemctl restart still-loading-receiver.service` on the board after sync.
  - Checks SSH reachability before attempting transfer and exits with a descriptive error if unreachable.
- Created `scripts/verify_hardware.sh` — pre-flight diagnostic script:
  - Checks macOS battery sensor (pmset), local relay (port 8765), board TCP reachability (port 8090), authenticated `/v1/lights`, and full Mac unit test suite.
  - On 26 October 2026 local run: battery sensor PASS (65% discharging), relay WARN (not started), board FAIL (127.0.0.1 used as test target, board offline), unit tests PASS (138 tests).

## Phase 11 decisions

- Built `mac-agent/terminal_monitor.py` — an ANSI terminal monitor and live matrix twin:
  - Standard library only (`math`, `time`, `os`, `json`, `urllib.request`, `argparse`).
  - Renders the exact 8×13 LED matrix frame timeline using 8-level grayscale glyphs (`·`, `░`, `▒`, `▓`, `█`).
  - Right column surfaces: current light state badge, job ID, progress bar, battery gauge with charging glyph, and Chrome download speed/bytes.
  - Interactive audition mode (`--demo`) cycles between running, slow, suspected stall, failed, completed, battery, and download states.
  - Connects to local relay (`--relay http://127.0.0.1:8765`) or board directly (`--board http://192.168.1.5:8090 --token ...`).
  - Displays Failure Intelligence alert box when a job failure occurs with root cause and suggested fix.
  - Restores terminal cursor cleanly on `SIGINT` (Ctrl+C).
  - Added 5 unit tests in `mac-agent/tests/test_terminal_monitor.py`. Total Mac agent unit test count reached 143 tests OK.

## Phase 12 decisions

- Created `scripts/test_all.sh` — a unified monorepo test runner:
  1. Runs all 143 Mac agent & shared protocol unit tests (`unittest discover`).
  2. Runs 2 telemetry relay unit tests (`relay/tests/test_relay.py`).
  3. Runs headless multi-scenario demo suite (`python3 mac-agent/demo.py --all --fast`).
  4. Runs 4 web frontend matrix engine tests (`npm test` in `web/`).
  5. Runs production web bundle build (`npm run build` in `web/`).
  - On 26 October 2026: all 5 test suites passed cleanly (149 total tests, exit 0).
- Created `.github/workflows/ci.yml`:
  - Multi-OS matrix: `ubuntu-latest` and `macos-latest`.
  - Python versions: `3.11`, `3.12`, `3.13`.
  - Node.js version: `20` with `npm` caching.
  - Automated verification of Python backend, relay, demo script, and TypeScript/Vite frontend on every push and pull request.

## Phase 13 decisions

- Built `shared/history_store.py` providing persistent job tracking and analytics across receiver and daemon restarts:
  - SQLite backend using standard-library `sqlite3` (thread-safe, zero external dependencies).
  - Schema stores: `job_id`, `event` (`completed` / `failed`), `start_time`, `end_time`, `duration_seconds`, `progress`, `exit_code`, `is_failure`, `message`, `category`, `summary`, `suggestion`, `excerpt`, `accepted_count`, and `highest_sequence`.
  - Automatic timestamp parsing (`_parse_timestamp`) supporting both ISO 8601 strings and Unix epoch floats.
  - Computes aggregate metrics: total jobs, completed vs failed counts, success rate %, average duration, total duration, and top failure categories.
  - Integrated into `shared/http_api.py`:
    - Automatically records jobs when terminal events (`completed` or `failed`) are accepted.
    - Exposes authenticated `GET /v1/history` (with `limit`, `offset`, and `failed_only` query parameters).
    - Exposes authenticated `GET /v1/history/stats` for aggregate metrics.
  - Added 3 unit tests in `mac-agent/tests/test_history_store.py`. Total Mac agent unit test count reached 146 tests OK.

## Phase 14 decisions

- Built `mac-agent/history_cli.py` for terminal-based historical queries:
  - `python3 mac-agent/history_cli.py`: displays clean ASCII table of past jobs (status badge, ID, duration, exit code, timestamp).
  - `python3 mac-agent/history_cli.py --failed`: filters to failed jobs, revealing diagnosis cause and recommended fix command.
  - `python3 mac-agent/history_cli.py --stats`: displays overall analytics summary (success rate, average run time, top failure categories).
  - Supports querying local SQLite store directly or querying an active UNO Q receiver over HTTP (`--board`, `--token`).
- Built `web/src/components/JobHistory.tsx` in the web frontend:
  - 4 KPI summary cards: Total Monitored Runs, Success Rate %, Avg Build Duration, Top Root Cause.
  - Filter toggle to view all jobs or failed jobs only.
  - Expandable row revealing Failure Intelligence: root cause summary, 1-click copyable resolution command, and sanitized terminal log excerpt.
  - Integrated into `web/src/App.tsx` on the Dashboard tab.
  - Added typed interfaces (`JobHistoryRecord`, `HistoryStats`) in `web/src/types/telemetry.ts` and realistic presets in `web/src/lib/demoData.ts`.
  - On 26 October 2026: `scripts/test_all.sh` verified all 152/152 tests across Python, Relay, and Web with exit code 0.

## Phase 15 decisions

- Built `mac-agent/audio.py` for ambient audible job notifications:
  - Non-blocking execution using `afplay` in a daemon thread (`threading.Thread`).
  - Standard macOS system sounds (`Glass.aiff` for completion chime, `Basso.aiff` for failure thud, `Tink.aiff` x2 for suspected stall).
  - Silent no-op on non-macOS environments so cross-platform CI is never broken.
  - Wired into `mac-agent/run_job.py` via the `--bell` flag.
  - Added 14 unit tests in `mac-agent/tests/test_audio.py`.
- Built `web/src/lib/audioCues.ts` Web Audio API sound synthesizer:
  - Zero external MP3/WAV audio files; synthesizes sine/triangle wave chimes in real-time.
  - Offline-ready and compliant with browser autoplay restrictions (initialized upon user toggle gesture).
  - Wired into `web/src/components/LiveDashboard.tsx` with mute/unmute control; fires only on live state transitions and never in demo mode or on initial mount.

## Phase 16 decisions

- Built `mac-agent/notifications.py` for native macOS Notification Center alerts:
  - Non-blocking execution via `osascript` in a daemon thread.
  - Emits native desktop notifications on job completion (`Job Completed` + elapsed time), job failure (`Job Failed` + root cause diagnosis summary), and suspected stall.
  - Robust escaping for AppleScript strings (quotes and backslashes).
  - Cross-platform silent no-op when `osascript` is unavailable.
  - Wired into `mac-agent/run_job.py` via the `--notify` CLI flag.
  - Added 12 unit tests in `mac-agent/tests/test_notifications.py`.
- Updated `scripts/test_all.sh`:
  - 172 Mac agent & shared protocol unit tests.
  - 2 Telemetry relay unit tests.
  - Multi-scenario demo suite verification (`--all --fast`).
  - 4 Web matrixEngine tests.
  - Production web bundle build (`tsc && vite build`).
  - Total automated test count reached 178 tests OK with 0 failures.

