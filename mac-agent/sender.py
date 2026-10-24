"""Send job events from the Mac to a Still Loading receiver.

A connection problem is reported as a delivery failure. It is not a job failure.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from messages import SIMULATOR_ONLY_EVENTS, WIRE_EVENTS


def _result(
    *,
    delivery: str,
    event_name: str,
    sequence: int | None,
    reason: str,
    detail: str,
    http_status: int | None = None,
    board_recorded_failure: bool = False,
) -> dict:
    return {
        "delivery": delivery,
        "delivered": delivery == "accepted",
        "event": event_name,
        "sequence": sequence,
        "reason": reason,
        "detail": detail,
        "http_status": http_status,
        # True only when the board accepted an event whose type is failed.
        "board_recorded_failure": board_recorded_failure,
    }


def post_event(base_url: str, token: str, event: dict, timeout: float = 2.0) -> dict:
    """POST one event. Network errors return a result instead of raising."""
    event_name = event.get("event") if isinstance(event, dict) else None
    sequence = event.get("sequence") if isinstance(event, dict) else None
    if isinstance(event_name, str) and event_name in SIMULATOR_ONLY_EVENTS:
        return _result(
            delivery="skipped",
            event_name=event_name,
            sequence=sequence if isinstance(sequence, int) else None,
            reason="simulator_only",
            detail="This event stays on the Mac. It is not sent to the board.",
        )

    body = json.dumps(event).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/v1/events",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"reason": "bad_response", "detail": raw[:200]}
        recorded = False
        delivery = "unauthorized" if exc.code == 401 else "rejected"
        return _result(
            delivery=delivery,
            event_name=str(event_name),
            sequence=sequence if isinstance(sequence, int) else None,
            reason=str(payload.get("reason", "rejected")),
            detail=str(payload.get("detail", "")),
            http_status=exc.code,
            board_recorded_failure=recorded,
        )
    except urllib.error.URLError as exc:
        return _result(
            delivery="connection_error",
            event_name=str(event_name),
            sequence=sequence if isinstance(sequence, int) else None,
            reason="connection_error",
            detail=str(exc.reason),
            board_recorded_failure=False,
        )

    accepted = status == 202 and payload.get("status") == "accepted"
    return _result(
        delivery="accepted" if accepted else "rejected",
        event_name=str(event_name),
        sequence=sequence if isinstance(sequence, int) else None,
        reason=str(payload.get("status", "")),
        detail="Receiver stored the event" if accepted else str(payload),
        http_status=status,
        board_recorded_failure=accepted and event_name == "failed",
    )


def get_job(base_url: str, token: str, job_id: str, timeout: float = 2.0) -> dict:
    """Read one job back. Network errors return delivery connection_error."""
    request = urllib.request.Request(
        base_url.rstrip("/") + "/v1/jobs/" + job_id,
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return {"delivery": "ok", "http_status": response.status, "body": payload}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"detail": raw[:200]}
        return {"delivery": "rejected", "http_status": exc.code, "body": payload}
    except urllib.error.URLError as exc:
        return {
            "delivery": "connection_error",
            "http_status": None,
            "body": {"reason": "connection_error", "detail": str(exc.reason)},
        }


def events_for_board(events: list[dict]) -> list[dict]:
    """Keep wire events. Leave simulator-only lines on the Mac."""
    return [event for event in events if event.get("event") in WIRE_EVENTS]
