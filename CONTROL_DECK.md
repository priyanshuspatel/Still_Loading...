# Still Loading — Control Deck

The browser is the demonstration surface. It asks a Mac control service for an allowlisted action. That service uses the existing readers, job runner, and receiver. The UNO Q still renders with its existing light codes. Gemma still runs on the Mac.

## Architecture

```text
Browser Control Deck
  POST /v1/control/<action>          GET /v1/control/state   (1s poll)
        |                                      ^
        v                                      |
mac-agent/control_deck.py                      |
  battery.py          read_macos_battery       |
  download_monitor.py ChromeDownloadDetector   |
  runner.py           fixed demo argv only     |
  gemma_analysis.py   after the failed event   |
  sender.py           existing posts           |
        |                                      |
        v                                      |
UNO Q receiver (uno-q/receiver.py, port 8090)
  POST /v1/events  /v1/battery  /v1/download
  POST /v1/display-mode  /v1/session/reset
  GET  /v1/lights  (App Lab / Bridge polls this)
        |
        v
App Lab Bridge -> sketch.ino 8×13 matrix
```

The receiver's `StateEngine` remains the source of truth for what the matrix is showing. The control service reads it back and mirrors it with `shared/matrix_display.py`, the same frames the sketch uses. The web matrix uses the matching `web/src/lib/matrixEngine.ts`.

Automatic priority is unchanged: an active download, then an active or failed job, then battery when return-to-battery is on, otherwise the job view.

## What the browser may ask for

`battery`, `download`, `job_success`, `job_slow`, `job_stall`, `job_failure`, `completed`, `idle`, `reset`, `stop`, `auto`, `job_mode`, `demo`.

A body that contains `command`, `argv`, `shell`, or `cmd` is rejected. There is no endpoint that runs an arbitrary shell line.

| Control | Existing code |
| --- | --- |
| Battery | Starts `battery_monitor.py --mode battery` once and keeps that process |
| Download | Starts `download_monitor.py --interval 0.25` once and keeps that process |
| Run Job / Completed | `run_process` with a fixed `python -c` argv |
| Slow | Scripted heartbeats, then a late progress event, so the receiver marks `slow` |
| Stall | Started job, then no further heartbeats, so the receiver watchdog marks `suspected_stall` |
| Failed | `run_process` posts `failed` immediately, then Gemma analyzes the redacted excerpt |
| Idle / Reset | `POST /v1/session/reset` clears the focused job and download |
| Demo | Local preview only for battery and download percentages, labeled `DEMO / SIMULATED` |

The deck does not show Slow, Stall, Auto Mode, or Job Mode buttons. Display mode stays `auto` unless a retained action, such as Battery or Run Job, selects a mode. The receiver still detects slow progress and stalls on its own.

## Real-time updates

The page polls `GET /v1/control/state` about once a second and pauses while the tab is hidden. The project did not already have a browser WebSocket. Polling matches the existing telemetry dashboard and is enough for a local demonstration. The public read-only relay in `relay/telemetry_relay.py` is unchanged.

`GET /api/telemetry` on the control service still returns the relay-shaped snapshot, so the developer dashboard can keep using it.

## Gemma

A failed demo job posts the `failed` event before model inference, so the matrix can change immediately. Gemma then runs on the Mac through the existing evidence check. The card shows `EVIDENCE VERIFIED` only when that check marks the cited line as found. If Gemma is off, the card says `Gemma unavailable — rules explanation used`.

## Run it

Terminal 1, receiver on the Mac for a loopback demo, or on the UNO Q for the board:

```bash
cd ~/still-loading
export STILL_LOADING_TOKEN='test-token-0123456789'
python3 uno-q/receiver.py --host 127.0.0.1 --port 8090
```

On the UNO Q, bind `0.0.0.0` and use the same token as `mac-agent/config.local.json`. App Lab keeps polling `GET /v1/lights`.

Terminal 2, control service:

```bash
cd ~/still-loading
export STILL_LOADING_TOKEN='test-token-0123456789'
python3 mac-agent/control_deck.py --host 127.0.0.1 --port 8080 --upstream http://127.0.0.1:8090
```

With a board config file:

```bash
python3 mac-agent/control_deck.py --host 127.0.0.1 --port 8080 --config mac-agent/config.local.json
```

Optional Gemma, still on the Mac:

```bash
export GEMMA_ENABLED=1 GEMMA_BASE_URL=http://127.0.0.1:11434/v1 GEMMA_MODEL=gemma2:2b
```

Terminal 3, web UI:

```bash
cd ~/still-loading/web
npm install
npm run dev
```

Open `http://127.0.0.1:5173` and choose **Control Deck**. Vite proxies `/v1` to port 8080.

## Hardware check

1. Start the UNO Q receiver and confirm App Lab is running the sketch.
2. Start the control service with `--config` pointed at the board.
3. Open the Control Deck. The header should read **UNO Q ● CONNECTED**.
4. **Battery** shows the Mac's real percentage on the page, the web matrix, and the physical matrix.
5. Start a Chrome download, then press **Download**. The percentage should advance on both matrices.
6. **Failed** turns the matrix to the X immediately, then fills the Gemma card.
7. Unplug or stop the receiver. The header should read **UNO Q ● OFFLINE** while the page and the last matrix preview remain. Start the receiver again and the header returns to connected without a browser reload.
