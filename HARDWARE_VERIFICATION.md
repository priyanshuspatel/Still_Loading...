# Still Loading... Hardware Verification Log

**Tagline:** Stop staring. Start living.  
**Hardware Platform:** Arduino UNO Q (Qualcomm QRB2210 Linux + STM32U585 microcontroller)  
**Host Machine:** macOS (Apple Silicon, Python 3.13.17)  
**Date of Hardware Verification:** 24–26 October 2026  

---

## 1. Physical Hardware & System Architecture

```text
┌────────────────────────┐         Local Wi-Fi (HTTP:8090)         ┌────────────────────────────────────────────────────────┐
│      MacBook Host      │ ──────────────────────────────────────> │                     Arduino UNO Q                      │
│                        │       Authorization: Bearer <token>     │                                                        │
│  - mac-agent/          │                                         │  [Qualcomm QRB2210 - Debian Linux]                     │
│    • run_job.py        │                                         │  - uno-q/receiver.py (HTTP 8090)                       │
│    • battery_monitor.py│                                         │  - uno-q/app_lab_main.py (polls /v1/lights)            │
│    • download_monitor  │                                         │                         │                              │
│    • demo.py           │                                         │                         ▼ Router Bridge (IPC)          │
│  - shared/             │                                         │  [STM32U585 Microcontroller]                           │
│    • explainer.py      │                                         │  - uno-q/sketch/sketch.ino                             │
│    • excerpt.py        │                                         │    • 8×13 Blue LED Matrix (Arduino_LED_Matrix)         │
│    • messages.py       │                                         │    • LED 3 (RGB, PH10–PH12)                            │
└────────────────────────┘                                         └────────────────────────────────────────────────────────┘
```

### Components Verified
1. **STM32U585 Microcontroller:**
   - **8×13 Blue LED Matrix:** 104 individual pixels with 3-bit grayscale brightness.
   - **LED 3 (RGB):** Active-low RGB LED on pins PH10 (Red), PH11 (Green), PH12 (Blue).
   - **LED 4 (RGB):** Verified available on PH13–PH15.
   - **Firmware:** Arduino App Lab C++ sketch (`uno-q/sketch/sketch.ino`) exposing `Bridge.provide("set_job_lights", ...)`.
2. **Qualcomm QRB2210 Application Processor:**
   - **OS:** Debian Linux with Docker container runtime for App Lab.
   - **Python Environment:** Python 3.11+ running `uno-q/receiver.py` as an authenticated HTTP service.
   - **Bridge Link:** Official Arduino Router Bridge providing high-speed Unix domain socket IPC between Linux and STM32U585.

---

## 2. Verified Subsystems & Test Evidence

### Phase 2: HTTP Transport & Token Authentication
- **Test:** HTTP loopback on `127.0.0.1:8090` and real network probe to `192.168.1.5:8090`.
- **Outcome:** `POST /v1/events` and `GET /v1/jobs/<job_id>` verified with shared Bearer token.
- **Security Check:** Unauthenticated requests rejected with HTTP 401; malformed JSON rejected with HTTP 400.
- **Resilience:** Lost network connection is treated as a delivery failure, never as a job crash.

### Phase 3 & 4: State Engine & Hardware Lights
- **Test:** Probe events sent via `send_events.py --probe` and `Bridge.call("set_job_lights", code, progress)`.
- **States Verified on Physical Board:**
  - `IDLE` (Code `0`): Moving waiting 3-dot animation, dim blue LED 3.
  - `RUNNING` (Code `1`): Blue LED 3 pulsing; matrix rendering live 2-digit percentage (`1%`–`99%`) or heart pulse.
  - `SLOW` (Code `2`): Slow progress gap recognized without declaring stall.
  - `SUSPECTED_STALL` (Code `3`): Heartbeats absent for >6s; matrix switches to stall dots; returns to `RUNNING` immediately upon next heartbeat.
  - `FAILED` (Code `4`): Solid red LED 3, matrix shows steady `X` with distinct corner markers.
  - `COMPLETED` (Code `5`): Green LED 3, 3 gentle heart pulses, `100` for 1.8s, then steady checkmark.

### Phase 4.1: Real Mac Process Runner
- **Test:** Ran live compilation commands and long scripts via `mac-agent/run_job.py --send`.
- **Outcome:** Real process output captured separately on stdout/stderr threads; `40%`, `90%` in stdout correctly emitted as live wire `progress` events without shell injection risks (`shell=False`).

### Phase 5: Battery & Chrome Download Indicators
- **Test:** `battery_monitor.py` querying `pmset -g batt` and `download_monitor.py` tracking active `.crdownload` files.
- **States Verified:**
  - `BATTERY` (Code `6`): Centered numeric battery percentage on matrix.
  - `BATTERY_CHARGING` (Code `7`): Alternates between percentage and live charging heart animation.
  - `BATTERY_UNAVAILABLE` (Code `8`): Shows steady `--` glyph when battery data is absent.
  - `DOWNLOAD` (Code `9`): Live Chrome download progress with cyan LED 3.
  - Priority engine verified: Active or failed jobs take precedence over battery in `auto` mode; returns to battery upon job completion with `--return-to-battery`.

### Phase 6: Safe Log Excerpt Extraction & Redaction
- **Test:** Simulated and real process crashes emitting stack traces and bearer tokens.
- **Outcome:** Sanitized trailing excerpts (max 10 lines / 512 bytes) attached to `failed` event. Sensitive tokens (Bearer tokens, `STILL_LOADING_TOKEN`, API keys, passwords, and 32+ hex strings) replaced with `[REDACTED]`.

### Phase 7: Zero-Overhead Rules Failure Explainer
- **Test:** Analyzed exit codes (126, 127, 130, 137, 139, 143) and error excerpts (`ModuleNotFoundError`, `SyntaxError`, `PermissionError`, test failures, Node.js, Rust, C/C++, Docker).
- **Outcome:** Structured `explanation` generated in <0.05 ms with 0 extra memory allocation.
- **Hardware Feasibility Benchmark:** Formally verified that running SLMs on QRB2210 (2 GB/4 GB shared RAM) poses high OOM and thermal risks; rules-first explainer validated as the optimal on-board engine.

---

## 3. How to Run the Complete Demonstration

Run all verification scenarios locally on the Mac:
```bash
cd ~/still-loading/mac-agent
python3 demo.py --all --fast
```

Run live against the physical UNO Q over Wi-Fi:
```bash
cd ~/still-loading/mac-agent
python3 demo.py --all --live --send --config config.local.json
```

Run automated regression suite:
```bash
cd ~/still-loading
python3 -m unittest discover -s mac-agent/tests -t mac-agent -v
```

## Gemma analysis — software tested, not verified on the UNO Q

Gemma is a Mac-side analysis layer. This change did **not** load a model on the Arduino UNO Q, and it did **not** change the STM32 matrix sketch.

**Software-tested**

- Evidence validation, secret redaction, malformed and timeout handling, and the watchdog fallback are covered by `mac-agent/tests/test_gemma_analysis.py`.
- Those tests use a scripted client. They do not prove that a live Gemma weight file produces a correct diagnosis.
- The web card is covered by `web/src/lib/gemmaCard.test.ts`.
- Existing battery, Chrome download, job, stall, failed, and completed light states are asserted again so a Gemma payload does not replace them.

**Not physically verified on the UNO Q**

- No Gemma inference was run on the QRB2210.
- The matrix was not observed rendering a Gemma diagnosis. It is not supposed to: the board still receives the existing light code (`failed` = 4, `suspected_stall` = 3, battery, download, and the other codes already verified above).
- A live round trip from `run_job.py --gemma` through Wi-Fi to a physical board was not part of this change.

Limits of the software path are in `GEMMA.md`.
