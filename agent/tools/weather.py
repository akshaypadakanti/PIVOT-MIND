"""Current weather via OpenWeatherMap. Never fakes results when unconfigured."""
from __future__ import annotations

from typing import Any

from django.conf import settings

from agent.services.http_client import HttpError, get_json

NAME = "weather"
CATEGORY = "External API"
DESCRIPTION = "Fetches live weather for a city: temperature, condition, humidity, and wind."
REQUIRES_API_KEY = "OPENWEATHERMAP_API_KEY"
EXAMPLES = [
    "What's the weather in Hyderabad?",
    "What is the temperature in London?",
    "Is it raining in Tokyo?",
]

SCHEMA = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "Get the current weather for a city using OpenWeatherMap. "
            "Use a city name such as Hyderabad, London, or Tokyo."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name, optionally with country code (for example Hyderabad or London,UK).",
                }
            },
            "required": ["city"],
        },
    },
}


def execute(city: str) -> dict[str, Any]:
    city = (city or "").strip()
    if not city:
        return {
            "success": False,
            "error": "Please provide a city name.",
            "summary": "Missing city name.",
            "data": {},
        }

    api_key = getattr(settings, "OPENWEATHERMAP_API_KEY", "") or ""
    if not api_key:
        message = "OpenWeatherMap API key is not configured. Set OPENWEATHERMAP_API_KEY to enable weather."
        return {"success": False, "error": message, "summary": message, "data": {"configured": False}}

    try:
        payload = get_json(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": city, "appid": api_key, "units": "metric"},
        )
    except HttpError as exc:
        if exc.status_code == 404:
            message = f"'{city}' was not recognized as a valid city."
            return {"success": False, "error": message, "summary": message, "data": {}}
        return {"success": False, "error": str(exc), "summary": str(exc), "data": {}}

    weather_list = payload.get("weather") or [{}]
    condition = weather_list[0].get("description", "Unknown").title()
    main = payload.get("main") or {}
    wind = payload.get("wind") or {}
    data = {
        "city": payload.get("name") or city,
        "country": (payload.get("sys") or {}).get("country", ""),
        "temperature_c": main.get("temp"),
        "feels_like_c": main.get("feels_like"),
        "condition": condition,
        "humidity": main.get("humidity"),
        "wind_speed_mps": wind.get("speed"),
        "units": "metric",
    }
    summary = (
        f"{data['city']}: {data['temperature_c']}°C, {condition}, "
        f"humidity {data['humidity']}%, wind {data['wind_speed_mps']} m/s"
    )
    return {"success": True, "error": None, "summary": summary, "data": data}
