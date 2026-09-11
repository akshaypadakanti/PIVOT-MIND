"""Date and time utilities using datetime and zoneinfo."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

NAME = "get_datetime"
CATEGORY = "Local"
DESCRIPTION = "Returns current date/time, timezone times, weekday, and days between dates."
REQUIRES_API_KEY = None
EXAMPLES = [
    "What is the current date?",
    "What time is it in Tokyo?",
    "What day of the week is it?",
    "How many days between 2026-01-01 and 2026-09-02?",
]

SCHEMA = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "Get the current date and time, convert to a timezone, report the weekday, "
            "or calculate the number of days between two ISO dates (YYYY-MM-DD)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "IANA timezone such as UTC, Asia/Tokyo, Asia/Kolkata, Europe/London.",
                },
                "start_date": {
                    "type": "string",
                    "description": "Optional start date in YYYY-MM-DD format for a day-count calculation.",
                },
                "end_date": {
                    "type": "string",
                    "description": "Optional end date in YYYY-MM-DD format for a day-count calculation.",
                },
            },
        },
    },
}

_COMMON_ZONES = {
    "utc": "UTC",
    "gmt": "UTC",
    "tokyo": "Asia/Tokyo",
    "japan": "Asia/Tokyo",
    "hyderabad": "Asia/Kolkata",
    "india": "Asia/Kolkata",
    "kolkata": "Asia/Kolkata",
    "ist": "Asia/Kolkata",
    "london": "Europe/London",
    "uk": "Europe/London",
    "new york": "America/New_York",
    "nyc": "America/New_York",
    "est": "America/New_York",
}


def _resolve_timezone(name: str | None) -> ZoneInfo:
    raw = (name or "UTC").strip()
    if not raw:
        raw = "UTC"
    mapped = _COMMON_ZONES.get(raw.lower(), raw)
    try:
        return ZoneInfo(mapped)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone '{name}'. Use an IANA name such as Asia/Tokyo.") from exc


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"'{value}' is not a valid date. Use YYYY-MM-DD.") from exc


def execute(
    timezone: str = "UTC",
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    try:
        zone = _resolve_timezone(timezone)
        now = datetime.now(zone)
        data: dict[str, Any] = {
            "timezone": str(zone),
            "current_date": now.date().isoformat(),
            "current_time": now.strftime("%H:%M:%S"),
            "iso": now.isoformat(timespec="seconds"),
            "day_of_week": now.strftime("%A"),
        }
        if start_date and end_date:
            start = _parse_date(start_date)
            end = _parse_date(end_date)
            data["start_date"] = start.isoformat()
            data["end_date"] = end.isoformat()
            data["days_between"] = (end - start).days
        elif start_date or end_date:
            raise ValueError("Provide both start_date and end_date to calculate days between dates.")
    except ValueError as exc:
        return {"success": False, "error": str(exc), "summary": str(exc), "data": {}}

    if "days_between" in data:
        summary = (
            f"{data['days_between']} days between {data['start_date']} and {data['end_date']}. "
            f"Current time in {data['timezone']}: {data['current_time']} on {data['day_of_week']}."
        )
    else:
        summary = (
            f"{data['current_date']} {data['current_time']} ({data['timezone']}), {data['day_of_week']}"
        )
    return {"success": True, "error": None, "summary": summary, "data": data}
