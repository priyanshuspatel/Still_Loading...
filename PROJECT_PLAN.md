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
│   ├── config.example.json   host, port, and token placeholders
│   └── tests/
├── shared/
│   ├── message_schema.json
│   ├── messages.py           validation and per-job sequence log
│   ├── http_api.py           receiver implementation
│   ├── state_engine.py       light state from accepted events
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
| 3 | State engine plus the first LED 3 and matrix sketch | Mac tests done in this session. The sketch has not been run on the board. |
| 4 | Confirm Bridge on the real board and adjust the sketch only if a light test fails | Waiting on the hardware steps in the README. |
| 4.1 | Watch one real Mac command and emit the existing job events | Mac tests in this session. The board protocol was not changed. |
| 5 | Matrix and RGB polish after a real look at the patterns | Not started |
| 6 | Short log excerpts on failure, still without an AI explanation | Not started. Phase 4.1 records the exit code and keeps the captured text off the wire. |
| 7 | Failure explanations. Rules first. A model only after a feasibility check. | Not started |
| 8 | Demo script and a list of what was verified on the hardware | Not started |

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
