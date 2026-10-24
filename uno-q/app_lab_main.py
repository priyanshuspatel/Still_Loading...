"""Paste this into the Python tab of the Arduino App Lab app.

It does not listen on port 8090. The SSH receiver already does that.
This loop reads the state file that receiver writes and forwards it to
the sketch with the official Bridge.call.

The file contains a job id and a light state. It does not contain the token.
"""

import json
import time
from pathlib import Path

from arduino.app_utils import App, Bridge

STATE_PATH = Path("/tmp/still-loading-lights.json")
_last_text = None


def loop():
    global _last_text
    try:
        text = STATE_PATH.read_text(encoding="utf-8")
    except OSError:
        time.sleep(0.2)
        return
    if text != _last_text:
        _last_text = text
        try:
            payload = json.loads(text)
            Bridge.call("set_job_lights", int(payload["code"]), int(payload["progress"]))
        except (OSError, ValueError, KeyError, TypeError):
            pass
    time.sleep(0.2)


App.run(user_loop=loop)
