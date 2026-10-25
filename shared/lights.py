"""Publish the current light state without waiting on an animation.

The HTTP handler calls this and returns. The microcontroller plays the
pattern on its own loop. On a Mac, Bridge is absent, so this prints the
state and can write a small JSON file for tests.
"""

from __future__ import annotations

import json
from pathlib import Path

from state_engine import LightView


class LightPublisher:
    def __init__(self, state_path: Path | None = None) -> None:
        self.state_path = state_path
        self.updates: list[LightView] = []

    def show(self, view: LightView) -> None:
        self.updates.append(view)
        print(
            f"lights {view.state} job={view.job_id} progress={view.progress} reason={view.reason}",
            flush=True,
        )
        if self.state_path is not None:
            payload = {
                "state": view.state,
                "code": view.code,
                "job_id": view.job_id,
                "progress": view.progress,
                "sequence": view.sequence,
            }
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
            temporary.write_text(json.dumps(payload), encoding="utf-8")
            temporary.replace(self.state_path)
        self._try_bridge(view)

    def _try_bridge(self, view: LightView) -> None:
        """Call the sketch when this process can see the UNO Q Bridge library.

        A missing library is normal on the Mac. The receiver keeps running.
        """
        try:
            from arduino.app_utils import Bridge
        except ImportError:
            return
        try:
            code = 1 if (view.state == "download" and not view.progress_known) else view.code
            prog = 0 if (view.state == "download" and not view.progress_known) else int(view.progress)
            Bridge.call("set_job_lights", code, prog)
        except Exception as exc:  # noqa: BLE001 - the light call must not stop HTTP
            print(f"lights call skipped ({exc.__class__.__name__})", flush=True)
