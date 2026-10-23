
import argparse
import json
import time
import uuid

HEARTBEAT_INTERVAL = 2.0


def emit(event, job_id, started, **extra):
    message = {
        "event": event,
        "job_id": job_id,
        "elapsed_seconds": round(time.monotonic() - started, 1),
        **extra,
    }
    print(json.dumps(message), flush=True)


def run(mode):
    job_id = str(uuid.uuid4())[:8]
    started = time.monotonic()
    duration = 20
    last_heartbeat = started
    last_progress = started
    progress = 0

    emit("started", job_id, started, mode=mode, progress=0)

    while True:
        now = time.monotonic()
        elapsed = now - started

        if mode == "fail" and elapsed >= 10:
            emit(
                "failed",
                job_id,
                started,
                progress=progress,
                message="Simulated build error",
            )
            return

        if elapsed >= duration:
            emit("completed", job_id, started, progress=100)
            return

        # Simulate a task that stops sending heartbeats.
        heartbeat_allowed = not (
            mode == "hang" and elapsed >= 8
        )

        if (
            heartbeat_allowed
            and now - last_heartbeat >= HEARTBEAT_INTERVAL
        ):
            last_heartbeat = now
            emit(
                "heartbeat",
                job_id,
                started,
                progress=progress,
            )

        progress_interval = 8 if mode == "slow" else 3

        if now - last_progress >= progress_interval:
            last_progress = now
            progress = min(99, int(elapsed / duration * 100))
            emit(
                "progress",
                job_id,
                started,
                progress=progress,
            )

        time.sleep(0.25)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Still Loading... heartbeat simulator"
    )
    parser.add_argument(
        "--mode",
        choices=["normal", "slow", "hang", "fail"],
        default="normal",
    )
    args = parser.parse_args()
    run(args.mode)
