# UNO Q receiver

`receiver.py` listens for JSON job events over Wi-Fi on port 8090. App Lab reads `GET /v1/lights` from that same receiver and calls Bridge. The two processes do not share `/tmp`.

Start it only after the board is on your Wi-Fi. The click-by-click setup, the token, and the Mac probe command are in the repository `README.md`.

From the board, with the `shared` and `uno-q` folders side by side:

```bash
cd ~/still-loading
export STILL_LOADING_TOKEN='the-same-token-as-on-the-mac'
python3 uno-q/receiver.py --host 0.0.0.0 --port 8090
```

`--host 0.0.0.0` means "accept connections from the local network." The Mac still uses the board's Wi-Fi IP or `name.local` address, never `0.0.0.0`.

The sketch in `sketch/sketch.ino` is what App Lab uploads to the microcontroller. Paste `app_lab_main.py` into that app's Python tab. The numbered clicks are in the repository README under "See the lights on the UNO Q". Run does flash the sketch. Do that only when you want to try the lights. The receiver command, port, and token stay the same.
