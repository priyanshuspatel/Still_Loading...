# Still Loading...

Stop staring. Start living.

Still Loading... is a small physical companion for long-running computer jobs. A Mac agent watches a job. An Arduino UNO Q will eventually show the status with its onboard lights.

The folder on disk is `still-loading`.

## Current status

**Phase 3 adds a light state engine.** The Wi-Fi receiver, port 8090, and token check are unchanged. You confirmed a probe to `192.168.1.5` stored a `started` event. The new engine can print `running`, `slow`, `suspected_stall`, `failed`, and `completed` on the board. The sketch that would drive LED 3 and the matrix is in the repo and has not been verified on the hardware yet.

| Piece | Status |
| --- | --- |
| Local job simulator | Working. |
| HTTP delivery and token check | Working. Your probe to `192.168.1.5:8090` was accepted. |
| State engine | Implemented and covered by Mac tests. |
| LED 3 and the 8×13 matrix | Sketch is written from the official Bridge and matrix examples. Not yet verified on the board. |
| Real command-line jobs | Not built. |
| AI error explanations | Not built. |

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

## Messages

Each wire message is one JSON object, schema version 1. The field list is in `shared/message_schema.json`.

Required on every message: `schema_version`, `event`, `job_id`, `sequence`, `timestamp`, `elapsed_seconds`, `progress`, `is_failure`.

Wire events: `started`, `heartbeat`, `progress`, `failed`, `completed`.

`failed` also needs `message` and a non-zero `exit_code`. `completed` needs `progress` 100 and `exit_code` 0.

The receiver keeps the highest sequence for each job id.

- A higher sequence is stored.
- The same sequence again is a duplicate and is refused.
- A lower sequence is stale and is refused.
- After `failed` or `completed`, a later sequence is refused.

A connection error is a delivery problem. The sender does not turn it into a job failure.

Transport, all from the Python standard library:

- `POST /v1/events` with `Content-Type: application/json` and `Authorization: Bearer <token>`
- `GET /v1/jobs/<job_id>` with the same header, to read the latest stored event
- `GET /v1/lights` returns the current light state and uses the same bearer token
- `GET /health` returns `{"status":"ok","service":"still-loading"}` and no job data

Default port: **8090**. The token is a shared secret you create. It is separate from your Wi-Fi password. Put it in `mac-agent/config.local.json`, which git ignores. Copy the shape from `mac-agent/config.example.json`.

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

On 24 October 2026 that command reported **20 tests, OK**, in about 3 seconds. Eight of those are the original simulator tests.

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

## Light states

The receiver decides the state on its own clock. A missing heartbeat is `suspected_stall`. It is not `failed`. `failed` happens only when a `failed` event is accepted.

| State | When it happens | LED 3 | Matrix (blue only) |
| --- | --- | --- | --- |
| `idle` | No job yet | Very dim | Three dots, one of them brighter |
| `running` | `started`, or a heartbeat after a stall | Slow blue pulse | Progress bar along the bottom |
| `slow` | Two progress events at least 6 seconds apart | Amber | Progress bar on a middle row |
| `suspected_stall` | No heartbeat for 6 seconds | Two magenta blinks, then a pause | Three dots |
| `failed` | Accepted `failed` event | Red | An X |
| `completed` | Accepted `completed` event | Green | A small check mark |

The matrix cannot show red, amber, or green. Those colors are on LED 3. LED 4 is unused. Linux LEDs 1 and 2 are unused.

The event replies are unchanged. The receiver prints a line such as `lights running job=abc progress=0`. App Lab does not read `/tmp/still-loading-lights.json`, because that folder is not shared with the App Lab process. App Lab calls `GET /v1/lights` on port 8090 with the same token, then `Bridge.call("set_job_lights", code, progress)`.

Test the engine on the Mac:

```bash
cd ~/still-loading
python3 -m unittest discover -s mac-agent/tests -t mac-agent -v
```

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

## What is next

AI explanations of log output stay for a later phase. The next check is the light test above.
