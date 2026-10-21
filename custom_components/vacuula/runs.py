"""Helpers that turn the server's raw run rows into tidy summaries."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

_EPOCH_MIN = datetime.min.replace(tzinfo=timezone.utc)


def parse_time(value: Any) -> datetime | None:
    """Parse an ISO string or epoch number into an aware UTC datetime."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 1e11 else value
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def summarize_run(row: dict[str, Any]) -> dict[str, Any]:
    """Summarise one row of GET /api/robot/<serial>/runs.

    The structure of ``timing`` and ``runs`` is copied from the robot by the
    server, so everything is parsed defensively: anything missing is None.
    """
    timing = row.get("timing")
    if not isinstance(timing, dict):
        timing = {}
    start = parse_time(timing.get("start"))
    end = parse_time(timing.get("end"))
    duration = None
    if start and end and end >= start:
        duration = round((end - start).total_seconds() / 60, 1)

    runs = row.get("runs")
    if isinstance(runs, dict):
        runs = [runs]
    if not isinstance(runs, list):
        runs = []

    area = 0.0
    area_found = False
    pickups = 0
    pickups_found = False
    states: list[str] = []
    for item in runs:
        if not isinstance(item, dict):
            continue
        stats = item.get("stats")
        if not isinstance(stats, dict):
            stats = {}
        value = _number(stats.get("area"))
        if value is not None:
            area += value
            area_found = True
        value = _number(stats.get("pickup_count"))
        if value is not None:
            pickups += int(value)
            pickups_found = True
        if isinstance(item.get("state"), str):
            states.append(item["state"])

    battery = _number(row.get("battery_consumed"))
    return {
        "id": row.get("id"),
        "floorplan": row.get("floorplan") or row.get("id"),
        "started_by": row.get("started_by"),
        "battery_consumed": battery,
        "complete": row.get("cleaning_complete"),
        "start": start,
        "end": end,
        "duration": duration,
        "area": round(area, 1) if area_found else None,
        "pickups": pickups if pickups_found else None,
        "charging": timing.get("charging"),
        "errors": timing.get("error"),
        "pauses": timing.get("pause"),
        "states": states,
    }


def end_key(summary: dict[str, Any]) -> datetime:
    """Sort key: newest run first when used with reverse=True."""
    return summary.get("end") or summary.get("start") or _EPOCH_MIN


def to_json(summary: dict[str, Any]) -> dict[str, Any]:
    """The summary with datetimes as ISO strings (for service responses)."""
    return {
        key: value.isoformat() if isinstance(value, datetime) else value
        for key, value in summary.items()
    }
