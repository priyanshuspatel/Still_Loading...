# Still Loading...

Stop staring. Start living.

Still Loading... is a small physical companion for long-running computer jobs. A Mac agent watches a job. An Arduino UNO Q will eventually show the status with its onboard lights.

The folder on disk is `still-loading`.

## Current status

**Phases 1 through 16 are fully implemented.** Physical hardware verification is documented in [HARDWARE_VERIFICATION.md](file:///Users/priyanshuswapneshpatel/still-loading/HARDWARE_VERIFICATION.md), and the repository is covered by **172 automated Mac tests**, **2 relay tests**, and **4 web matrix tests** (178 total tests).

| Piece | Status |
| --- | --- |
| Local job simulator | Working. |
| HTTP delivery and token check | Working. Verified against `192.168.1.5:8090`. |
| State engine | Implemented and covered by Mac tests. |
| LED 3 and the 8×13 matrix | Phase 4 verified on hardware. Phase 5 adds heartbeats, waiting dots, numeric `%`, battery mode, and download mode. |
| Real command-line jobs | Phase 4.1 verified on hardware (`run_job.py`). |
| MacBook battery indicator | Continuous polling (`battery_monitor.py`, 15s default, backoff + 5m refresh). Covered by Mac tests. |
| Chrome download monitor | Real-time percentage (`download_monitor.py`). Covered by Mac tests. |
| Safe failure log excerpts | Phase 6 working: extracts trailing error lines (max 512 chars) with secret redaction. |
| Failure explanations | Phase 7 working: zero-overhead rules-first explainer + hardware model feasibility benchmark. |
| Full demo & verification | Phase 8 working: unified demo script (`demo.py`) and [HARDWARE_VERIFICATION.md](file:///Users/priyanshuswapneshpatel/still-loading/HARDWARE_VERIFICATION.md). |
| Failure intelligence web dashboard | Phase 9 working: surfaces root cause diagnosis, suggested fixes with 1-click copy, and redacted excerpts. |
| Daemons & operational tooling | Phase 10 working: systemd receiver service, macOS launchd agents, sync script, and diagnostic hardware verifier. |
| Live ANSI terminal monitor | Phase 11 working: zero-dependency terminal companion (`terminal_monitor.py`) with live 8×13 matrix twin. |
| Unified test runner & CI/CD | Phase 12 working: single-command test runner (`scripts/test_all.sh`) and GitHub Actions CI workflow. |
| Persistent History & Analytics Store | Phase 13 working: SQLite store (`history_store.py`) tracking runs, duration, and stats across receiver restarts. |
| Job History UI & CLI Viewer | Phase 14 working: web component (`JobHistory.tsx`) and CLI (`history_cli.py`) with metrics, filtering, and fix copy. |
| Ambient Audio Cues | Phase 15 working: macOS system sounds (`audio.py`, `--bell`) & Web Audio synthesizer (`audioCues.ts`). |
| Native macOS Notifications | Phase 16 working: Notification Center alerts (`notifications.py`, `--notify`). |

## Run the full demonstration

To test and visualize all scenarios (Normal, Slow, Hang, Fail, Real Process Crash with Explanation, and MacBook Battery) in under 3 seconds:

```bash
cd ~/still-loading/mac-agent
python3 demo.py --all --fast
```

To run in real time:
```bash
python3 demo.py --all --live
```

To forward the entire demo to your live UNO Q hardware:
```bash
python3 demo.py --all --send --config config.local.json
```

## Control Deck

The browser Control Deck is the demonstration surface. It calls `mac-agent/control_deck.py`, which uses the existing battery reader, Chrome download monitor, job runner, and receiver. The map and the start commands are in [CONTROL_DECK.md](CONTROL_DECK.md).

```bash
cd ~/still-loading
export STILL_LOADING_TOKEN='test-token-0123456789'
python3 uno-q/receiver.py --host 127.0.0.1 --port 8090
```

```bash
python3 mac-agent/control_deck.py --host 127.0.0.1 --port 8080 --upstream http://127.0.0.1:8090
```

```bash
cd ~/still-loading/web && npm run dev
```

CLI commands such as `run_job.py`, `battery_monitor.py`, and `download_monitor.py` stay available.

## Run the simulator

Python 3.11 or newer is enough. This Mac was checked with Python 3.13.17. There are no packages to install.

```bash
cd ~/still-loading/mac-agent
python3 --version
python3 job_agent.py --mode fail --fast
```

| Mode | What you should see | How it ends |
| --- | --- | --- |
| `normal` | Heartbeat every 2 seconds, progress every 3 seconds | `completed` at 20 seconds, progress 100 |
| `slow` | Same heartbeats, progress at 8 seconds (40) and 16 seconds (80) | `completed` at 20 seconds |
| `hang` | Heartbeats stop at 8 seconds. Progress can still continue. | `scenario_ended`. `is_failure` stays false |
| `fail` | Heartbeats and progress until 10 seconds | `failed`, `is_failure` true, `exit_code` 1 |

Leave `--fast` off to watch a run in real time. `fail` takes about 10 seconds. The other modes take about 20 seconds.

`heartbeat_paused` and `scenario_ended` are notes for you at the terminal. The sender does not forward them.

## Run a real command

The simulator is still there. This command watches a real program instead. Put the program and its arguments after `--`. They are started as a normal process, not as a shell line.

```bash
cd ~/still-loading/mac-agent
python3 run_job.py -- python3 -c "import time; print('working 40%'); time.sleep(3); print('working 90%')"
```

Stdout shows JSON events: `started`, a `heartbeat` about every 2 seconds, `progress` when a line contains a percent, then `completed` or `failed`. A quiet command that prints nothing still ends as `completed` when its exit code is 0. Exit code 0 is `completed`. Any other exit code is `failed`.

When a command fails (exit code != 0), a safe trailing excerpt from stderr (falling back to stdout, capped at 10 lines and 512 characters) is sanitized and attached to the `failed` event as `"excerpt"`. Bearer tokens, Authorization headers, and sensitive key/password assignments are automatically redacted with `[REDACTED]`. Use `--no-excerpt` if you want to omit the log excerpt entirely.

Add `--gemma` to ask a local or remote Gemma endpoint to explain that excerpt. The rules explainer still runs if Gemma is off, slow, or returns a citation that is not in the log. Gemma runs on the Mac. The UNO Q keeps its existing light codes. See `GEMMA.md`.

```bash
GEMMA_ENABLED=1 GEMMA_BASE_URL=http://127.0.0.1:11434/v1 GEMMA_MODEL=gemma2:2b \
  python3 run_job.py --gemma -- python3 -c "import non_existent_pkg_xyz"
```

The command's full stdout and stderr stay on the Mac and are not copied into the JSON. The last stderr line of `run_job.py` itself shows the process id, elapsed time, exit code, and how many bytes were captured.

To send that same run to a receiver you already started, add `--send`. This uses the existing token and does not print it:

```bash
python3 run_job.py --send --config config.local.json -- python3 -c "import time; time.sleep(3)"
```

## Messages

Each wire message is one JSON object, schema version 1. The field list is in `shared/message_schema.json`.

Required on every message: `schema_version`, `event`, `job_id`, `sequence`, `timestamp`, `elapsed_seconds`, `progress`, `is_failure`.

Wire events: `started`, `heartbeat`, `progress`, `failed`, `completed`.

`failed` also needs `message` and a non-zero `exit_code`, and can include an optional sanitized `excerpt` string (max 512 characters). `completed` needs `progress` 100 and `exit_code` 0. Neither `completed` nor intermediate events take an `excerpt` or `message`.

The receiver keeps the highest sequence for each job id.

- A higher sequence is stored.
- The same sequence again is a duplicate and is refused.
- A lower sequence is stale and is refused.
- After `failed` or `completed`, a later sequence is refused.

A connection error is a delivery problem. The sender does not turn it into a job failure.

Transport, all from the Python standard library:

- `POST /v1/events` with `Content-Type: application/json` and `Authorization: Bearer <token>`
- `GET /v1/jobs/<job_id>` with the same header, to read the latest stored event
- `POST /v1/battery` and `GET /v1/battery` with the same bearer token, for validated MacBook battery readings
- `POST /v1/download` and `GET /v1/download` with the same bearer token, for validated Chrome download progress
- `POST /v1/display-mode` with the same bearer token, to choose `auto`, `job`, or `battery` display priority
- `GET /v1/lights` returns the current light state and uses the same bearer token
- `GET /health` returns `{"status":"ok","service":"still-loading"}` and no job data

Default port: **8090**. The token is a shared secret you create. It is separate from your Wi-Fi password. Put it in `mac-agent/config.local.json`, which git ignores. Copy the shape from `mac-agent/config.example.json`. Never hard-code, print, or commit the bearer token. If a token was ever exposed in terminal logs or screenshots, rotate it separately and synchronize the new token across `mac-agent/config.local.json`, the UNO Q SSH receiver (`STILL_LOADING_TOKEN`), and App Lab (`TOKEN_OVERRIDE` or `~/still-loading-token`).

## Practice on the Mac before using the board

Terminal 1:

```bash
cd ~/still-loading
export STILL_LOADING_TOKEN='test-token-0123456789'
python3 uno-q/receiver.py --host 127.0.0.1 --port 8090
```

Terminal 2:

```bash
cd ~/still-loading/mac-agent
python3 send_events.py --probe --url http://127.0.0.1:8090 --token 'test-token-0123456789' --job-id probe0001
```

Success looks like `accepted started sequence=1` in Terminal 2, and `accepted job probe0001 sequence 1 started` in Terminal 1. Then press Control-C in Terminal 1.

This loopback run stays on the Mac. It is not the UNO Q.

## Run the tests

```bash
cd ~/still-loading
python3 -m unittest discover -s mac-agent/tests -t mac-agent -v
```

The suite covers the simulator, the HTTP protocol, the state engine, light forwarding, the local process runner, the 8×13 matrix frames, the Chrome download monitor, and the continuous MacBook battery monitor. It does not contact the Arduino. On 25 October 2026 that command reported **74 tests, OK**.

## Put the receiver on the UNO Q

Do this only when you want the real board in the loop. Use a **USB-C data cable** (a charge-only cable is not enough) the first time. The password you type belongs in Arduino App Lab and in the SSH prompt. Do not put it in this repository.

1. Open **Arduino App Lab** on the Mac.
2. Connect the UNO Q with the USB-C data cable. In the board list, choose the board that shows a USB icon.
3. If a setup wizard appears, give the board a name, a Linux password for the user `arduino`, and your Wi-Fi network. The name you choose becomes `that-name.local` on the network. Official steps: [Connect and configure a board](https://docs.arduino.cc/software/app-lab/configure/config/).
4. Wait until the board finishes booting. The LED matrix plays a boot animation for about 20–30 seconds. Leave the matrix alone during that time.
5. Open **Settings** (the control in App Lab for the connected board). Under **Network Connections**, write down the **IP** address. Under **System Info**, confirm **Remote access (SSH)** is enabled. It is on by default. Official page: [App Lab settings](https://docs.arduino.cc/software/app-lab/configure/settings/).
6. On the Mac, create a token and a config file. Replace the host with the name or IP from step 5.

   ```bash
   cd ~/still-loading/mac-agent
   python3 -c "import secrets; print(secrets.token_hex(16))"
   ```

   Save `mac-agent/config.local.json`:

   ```json
   {
     "host": "the-name-you-chose.local",
     "port": 8090,
     "token": "paste-the-token-here"
   }
   ```

7. Copy the receiver to the board. Replace the host with the same name or IP.

   ```bash
   cd ~/still-loading
   ssh arduino@the-name-you-chose.local 'mkdir -p ~/still-loading'
   scp -r shared uno-q arduino@the-name-you-chose.local:~/still-loading/
   ```

   The first SSH connection asks you to trust the fingerprint. Type `yes`, then the Linux password from step 3.

8. Start the receiver over SSH. This does not use App Lab's **Run** button, so it does not flash the microcontroller.

   ```bash
   ssh arduino@the-name-you-chose.local
   cd ~/still-loading
   export STILL_LOADING_TOKEN='paste-the-same-token'
   python3 uno-q/receiver.py --host 0.0.0.0 --port 8090
   ```

   Leave this window open. You should see `Still Loading receiver listening on http://0.0.0.0:8090`.

9. From a second Mac terminal, send one probe:

   ```bash
   cd ~/still-loading/mac-agent
   python3 send_events.py --probe --config config.local.json
   ```

   Success on the Mac: `Read back from the receiver` with `event=started` and `sequence=1`, and the command exits 0.

   Success on the board: a line `accepted job ... sequence 1 started`.

10. Paste both of those lines back into the chat. That is the evidence for a real Mac-to-board message.

If the Mac prints `connection_error`, the job was not marked failed. Check that the receiver window is still open, that the host in `config.local.json` matches Settings, and that the token matches on both sides.

## Light states and 8×13 matrix animations

The receiver decides the state on its own clock. A missing heartbeat is `suspected_stall`. It is not `failed`. `failed` happens only when a `failed` event is accepted. All animations run locally on the STM32 microcontroller using `millis()` so `Bridge` and HTTP are never blocked.

| Code | State | When it happens | LED 3 | 8×13 Matrix (blue only) |
| --- | --- | --- | --- | --- |
| `0` | `idle` | No job yet | Calm dim neutral | Three waiting dots (`...`), stepping gently |
| `1` | `running` | `started`, or a heartbeat after a stall | Calm blue breathing pulse | Blinks a centered heart twice on start, then cycles between numeric `%` (when known), three waiting dots (`...`), and an occasional gentle heart pulse |
| `2` | `slow` | Two progress events at least 6 seconds apart | Warm amber | Shows known `%` (with corner slow ticks) and slower two-row waiting dots (`...`) |
| `3` | `suspected_stall` | No heartbeat for 6 seconds | Gentle magenta/amber pulse | Framed exclamation warning (`[ ! ]`), distinct from waiting dots and `X` |
| `4` | `failed` | Accepted `failed` event | Steady red | Steady `X` with corner markers until a new job arrives or display mode changes |
| `5` | `completed` | Accepted `completed` event | Calm green | Blinks the heart 3 times, shows `100` with a full bottom bar, then settles into a steady checkmark |
| `6` | `battery` | Battery mode when discharging or full | Calm teal (or green at 100%) | Live battery percentage (`0%`–`99%`, or `100` with full bottom bar) |
| `7` | `battery_charging` | Battery mode while actively charging | Warm green-cyan | Live battery percentage plus an animated bottom charging bar |
| `8` | `battery_unavailable` | Battery mode before any battery reading arrives | Dim neutral | Neutral `--` dashes (never a fabricated `0%`) |
| `9` | `download` | Active Chrome download in `auto` mode | Cyan-blue (green at 100%) | Live download percentage (`0%`–`99%`), then `100` briefly and a completion checkmark |

### How percentages fit on the 8×13 matrix
- **`1%` to `99%` (and `0%` in battery mode):** Uses a 3×5 pixel font on rows 1–5 with a 3×5 `%` sign (`1%`–`9%` centered across 7 columns; `10%`–`99%` across 11 columns) plus a proportional progress bar on row 7.
- **`100%` compact representation:** Three digits plus `%` would require 15 columns on a 13-column display. Instead, `100%` is rendered as `100` (three 3×5 digits across columns 1–11) paired with a full 13-pixel completion/charged bar across row 7.
- **Unknown progress:** When a job has not reported an explicit percentage yet, the matrix shows the waiting dots (`...`) and occasional heartbeat rather than a fake `0%`.

The matrix cannot show red, amber, or green. Those colors are on LED 3. LED 4 is unused. Linux LEDs 1 and 2 are unused.

The event replies are unchanged. The receiver prints a line such as `lights running job=abc progress=0`. App Lab does not read `/tmp/still-loading-lights.json`, because that folder is not shared with the App Lab process. App Lab calls `GET /v1/lights` on port 8090 with the same token, then `Bridge.call("set_job_lights", code, progress)`.

## MacBook battery indicator and display priority

You can use the UNO Q as a continuous desk battery gauge that automatically updates whenever your MacBook's battery percentage or charging state (`charging`, `discharging`, `full`, `unknown`) changes.

### Start and stop continuous battery monitoring
1. **Preview locally (one-time diagnostic, no board required):**
   ```bash
   cd ~/still-loading/mac-agent
   python3 battery_monitor.py --once --dry-run
   ```
2. **Start continuous battery monitoring in battery display mode (polls every 15s by default):**
   ```bash
   cd ~/still-loading/mac-agent
   python3 battery_monitor.py --mode battery --config config.local.json
   ```
3. **Start continuous background battery updates without changing the current display mode:**
   ```bash
   cd ~/still-loading/mac-agent
   python3 battery_monitor.py --config config.local.json
   ```
4. **Customize the polling or periodic refresh intervals:**
   - `--interval SECONDS`: seconds between local `pmset -g batt` checks (default `15`).
   - `--refresh-interval SECONDS`: re-send an unchanged reading every `SECONDS` (default `300` = 5 minutes; `0` disables) so the UNO Q automatically recovers if the receiver is restarted.
   - `--once`: read and send one battery update, then exit.
5. **Stop cleanly:** Press **Control-C** (`SIGINT`) at any time. The monitor exits cleanly with code `130`.

### Select display mode and priority
- **Default priority (`auto`):** Active Chrome downloads (`download`, code `9`), active jobs (`running`, `slow`, `suspected_stall`), and `failed` jobs always take priority over background battery updates so a battery poll never hides a build failure or active download.
- **Switch explicitly to battery mode:**
   ```bash
   cd ~/still-loading/mac-agent
   python3 battery_monitor.py --mode battery --config config.local.json
   ```
   Or switch the mode immediately without starting a polling loop:
   ```bash
   python3 battery_monitor.py --set-mode battery --config config.local.json
   ```
   If no battery reading has arrived yet, the matrix shows `--` (`battery_unavailable`, code `8`) rather than a fabricated percentage.
- **Return to automatic priority (`auto`) or job-only mode (`job`):**
   ```bash
   python3 battery_monitor.py --set-mode auto --config config.local.json
   python3 battery_monitor.py --set-mode job --config config.local.json
   ```
- **Automatically return to battery after a job or download completes (`auto` mode):**
   Pass `--return-to-battery` (either on `battery_monitor.py` or when starting `uno-q/receiver.py`):
   ```bash
   python3 battery_monitor.py --return-to-battery --config config.local.json
   ```
   While a job or download is active, its progress stays in front. Once it completes, the display switches back to the live battery percentage.

### Troubleshooting and resilience
- **Temporary receiver or Wi-Fi outage:** If the UNO Q receiver is temporarily unreachable, `battery_monitor.py` keeps running, logs the delivery error to stderr, does **not** mark the failed reading as sent, and retries with exponential backoff (`15s -> 30s -> 60s` cap). As soon as connectivity recovers, it immediately sends the latest battery percentage and charging state and resets its poll interval to `15s`.
- **Receiver restarted:** Even if your MacBook battery sits steady (for example at `100%` or `80%`), the 5-minute periodic refresh (`--refresh-interval 300`) repopulates the receiver automatically without manual reruns.

### Important limitation when the MacBook lid is closed
macOS puts a MacBook to sleep when its lid is closed unless supported clamshell conditions (external display + power) or an explicit user sleep override keep the system awake.
- **What happens during sleep:** When macOS sleeps, user-space Python processes pause and stop sending HTTP updates. The UNO Q will keep showing the last state it received before the Mac went to sleep; it cannot receive new battery percentages from a sleeping Mac.
- **Practical test:** Run `python3 battery_monitor.py --mode battery --config config.local.json` with the lid open and verify the percentage and charging animation on the matrix. If you want updates with the lid closed while charging on a desk without an external monitor, you must explicitly keep the Mac awake during that charge session (and restore normal sleep afterward). Never assume the battery display is live if the Mac has gone to sleep.

## See the lights on the UNO Q

Your receiver is already running the previous code. Restart it so it loads the state engine. Use the same token you already exported. Do not create a new one.

1. In the SSH window where `receiver.py` is running, press Control-C.
2. On the Mac, copy the updated files. This does not copy `config.local.json`.

   ```bash
   cd ~/still-loading
   scp -r shared uno-q arduino@192.168.1.5:~/still-loading/
   ```

3. On the board, start the same receiver again:

   ```bash
   ssh arduino@192.168.1.5
   cd ~/still-loading
   export STILL_LOADING_TOKEN='the token you already use'
   python3 uno-q/receiver.py --host 0.0.0.0 --port 8090
   ```

   You should see `Still Loading receiver listening on http://0.0.0.0:8090`.
4. On the Mac, send the same probe as before:

   ```bash
   cd ~/still-loading/mac-agent
   python3 send_events.py --probe --config config.local.json
   ```

   The SSH window should add `lights running`. About 6 seconds later it should add `lights suspected_stall`. That stall is the missing heartbeat. It is not a failure.
5. Open the App Lab app you already uploaded. Replace the Python tab with the new `uno-q/app_lab_main.py`. In that editor, set `TOKEN_OVERRIDE` to the same token the SSH receiver already uses. Leave that change on the board. Do not copy it back into git, and do not make a new token.
6. If the App Lab log later says the lights endpoint is unreachable, also set `LIGHTS_URL_OVERRIDE = "http://192.168.1.5:8090"`.
7. Press **Run** in App Lab. The sketch can stay as it is if it already contains `set_job_lights`. Leave the SSH receiver running. This Python file does not listen on port 8090.
8. Send the probe from step 4 again. The App Lab log should show `forwarded running code=1 progress=0`. LED 3 should pulse blue. About 6 seconds later the log should show `forwarded suspected_stall`. The moving three dots you see before that are the idle pattern, because no light code has arrived yet. If SSH prints `lights running` and App Lab prints `unreachable`, paste both logs here and leave the token out.

To see red, from the Mac:

```bash
python3 send_events.py --mode fail --fast --config config.local.json
```

The board should end on `lights failed`. LED 3 should be red and the matrix should show an X, once the sketch is running.

## Web Dashboard & Failure Intelligence (Phase 9)

A responsive, high-performance web dashboard is available in `web/` and deployed at [stillloading.tech](https://stillloading.tech):
- **Live Failure Intelligence Card:** When a job fails, the dashboard surfaces a root cause diagnosis, suggested command resolution with a 1-click clipboard copy button, and a sanitized terminal excerpt (`max 10 lines / 512B`) with secrets redacted.
- **Physical Matrix Twin (8×13):** A pixel-perfect canvas twin mirroring the STM32U585 LED matrix firmware with interactive state audition (Normal, Slow, Hang, Fail, Completed, Battery Charging, Battery Discharging, Battery Unavailable, and Chrome Downloads).
- **Chrome Download & Battery Monitors:** Real-time transfer rates, percentage gauges, and time remaining.

### Running the Web Dashboard Locally
```bash
cd ~/still-loading/web
npm install
npm test          # Runs matrixEngine.test.ts (4/4 tests pass)
npm run dev       # Starts local Vite development server
```

---

## Operational Tooling & Background Daemons (Phase 10)

### 1. Board Synchronization (`scripts/sync_to_board.sh`)
Quickly sync `shared/` and `uno-q/` to the Arduino UNO Q over SSH/rsync without copying local credentials or `.DS_Store` files:

```bash
# Sync to default board IP (192.168.1.5)
./scripts/sync_to_board.sh

# Sync to a custom IP and restart the systemd receiver service:
./scripts/sync_to_board.sh 192.168.1.10 --restart
```

### 2. Pre-Flight Diagnostic Verifier (`scripts/verify_hardware.sh`)
Runs a comprehensive pre-flight check covering local macOS battery sensors, telemetry relay reachability, board connectivity (`port 8090`), authenticated `/v1/lights`, and the full unit test suite:

```bash
./scripts/verify_hardware.sh [BOARD_IP] [TOKEN]
```

### 3. Persistent UNO Q Receiver Daemon (`systemd`)
To start the receiver automatically on the Qualcomm QRB2210 Linux OS at boot:

```bash
# From the board (ssh arduino@192.168.1.5)
sudo cp ~/still-loading/uno-q/still-loading-receiver.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now still-loading-receiver.service

# Check status and logs:
sudo systemctl status still-loading-receiver.service
journalctl -u still-loading-receiver.service -f
```

### 4. Background macOS Agents (`launchd`)
To run battery monitoring and telemetry relay in the background on your Mac without keeping terminal windows open, use the Property List templates in `mac-agent/launchd/`:
- `mac-agent/launchd/com.stillloading.battery.plist` (polls `pmset -g batt` every 15s)
- `mac-agent/launchd/com.stillloading.relay.plist` (serves the web dashboard on `127.0.0.1:8765`)

See [`mac-agent/launchd/README.md`](file:///Users/priyanshuswapneshpatel/still-loading/mac-agent/launchd/README.md) for full click-by-click installation instructions.

---

## Live Terminal Monitor & Matrix Twin (Phase 11)

For developers who prefer staying in their terminal, `mac-agent/terminal_monitor.py` provides a zero-dependency ANSI dashboard:
- **ASCII 8×13 Matrix Twin:** Visualizes the UNO Q matrix with 8 levels of grayscale shading in real-time.
- **Side-by-side Telemetry:** Displays state badge, active job progress bar, MacBook battery percentage with charging glyph, and Chrome download speed.
- **Failure Intelligence Alert:** Instantly displays root cause diagnosis and suggested fix if a job fails.

```bash
# Run in interactive state demo/audition mode:
python3 mac-agent/terminal_monitor.py --demo

# Connect to a live local telemetry relay:
python3 mac-agent/terminal_monitor.py --relay http://127.0.0.1:8765

# Connect directly to the UNO Q board:
python3 mac-agent/terminal_monitor.py --board http://192.168.1.5:8090 --token $STILL_LOADING_TOKEN
```

---

## Unified Test Runner & CI/CD (Phase 12)

### Run All Monorepo Tests Locally
Execute the complete test suite across Python, Relay, and Web with one command:

```bash
./scripts/test_all.sh
```

This verifies:
1. **146 Mac Agent & Shared Protocol tests** (`unittest discover`)
2. **2 Telemetry Relay tests** (`relay/tests/test_relay.py`)
3. **Headless multi-scenario Demo Suite** (`demo.py --all --fast`)
4. **4 Web Matrix Engine tests** (`npm test` in `web/`)
5. **Vite Production Bundle Build** (`npm run build` in `web/`)

### Automated GitHub Actions CI
The workflow in [`.github/workflows/ci.yml`](file:///Users/priyanshuswapneshpatel/still-loading/.github/workflows/ci.yml) automatically runs on push and pull request across:
- **Operating Systems:** `ubuntu-latest`, `macos-latest`
- **Python Versions:** 3.11, 3.12, 3.13
- **Node.js:** 20 (with npm caching)

---

## Job History & Analytics (Phases 13 & 14)

### 1. Terminal History Query (`mac-agent/history_cli.py`)
Query recorded build and test sessions without starting a browser:

```bash
# List recent jobs (status, duration, exit code, timestamp):
python3 mac-agent/history_cli.py

# Show overall metrics (success rate, average run time, top failure categories):
python3 mac-agent/history_cli.py --stats

# Show failed jobs only with diagnosis and 1-click suggested fix:
python3 mac-agent/history_cli.py --failed

# Query history from a live UNO Q receiver over HTTP:
python3 mac-agent/history_cli.py --board http://192.168.1.5:8090 --token $STILL_LOADING_TOKEN
```

### 2. Web Analytics & Session Log (`JobHistory.tsx`)
On the web dashboard's **Live Dashboard** tab:
- **KPI Summary Grid:** Real-time visibility into Total Monitored Runs, Overall Success Rate (%), Average Duration (seconds), and Top Root Cause.
- **Interactive Execution Log:** Filter between all jobs and failed-only runs.
- **Expandable Failure Details:** Click any failed job to view root cause diagnosis, suggested command resolution with a 1-click **Copy** button, and sanitized terminal output excerpts.
- **Receiver Endpoints:**
  - `GET /v1/history?limit=50&offset=0&failed_only=1`
  - `GET /v1/history/stats`


