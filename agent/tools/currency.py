"""Currency conversion with optional live API and labelled demo rates."""
from __future__ import annotations

from typing import Any

from django.conf import settings

from agent.services.http_client import HttpError, get_json

NAME = "currency_converter"
CATEGORY = "External API"
DESCRIPTION = "Converts currency amounts. Uses a live API when configured; otherwise labelled demo rates."
REQUIRES_API_KEY = "CURRENCY_API_KEY"
EXAMPLES = [
    "Convert 100 USD to INR",
    "Convert 5000 INR to USD",
    "How much is 50 EUR in USD?",
    "Convert 25 USD to EUR",
]

# Static educational rates. These are NOT live market prices.
DEMO_RATES_TO_USD = {
    "USD": 1.0,
    "INR": 0.012,
    "EUR": 1.08,
    "GBP": 1.27,
    "JPY": 0.0067,
}
DEMO_MODE_LABEL = "DEMO MODE — static educational rates, not live market data."

SCHEMA = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "Convert an amount from one currency to another. "
            "Supported examples: USD to INR, INR to USD, EUR to USD, USD to EUR. "
            "If a live currency API key is not configured, results are clearly labelled as demo rates."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "The amount of money to convert."},
                "from_currency": {
                    "type": "string",
                    "description": "ISO currency code of the source, for example USD, INR, EUR.",
                },
                "to_currency": {
                    "type": "string",
                    "description": "ISO currency code of the target, for example INR, USD, EUR.",
                },
            },
            "required": ["amount", "from_currency", "to_currency"],
        },
    },
}


def _code(value: str) -> str:
    code = (value or "").strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise ValueError(f"'{value}' is not a valid 3-letter currency code.")
    return code


def _demo_convert(amount: float, source: str, target: str) -> tuple[float, float]:
    if source not in DEMO_RATES_TO_USD or target not in DEMO_RATES_TO_USD:
        supported = ", ".join(sorted(DEMO_RATES_TO_USD))
        raise ValueError(f"Demo mode supports {supported} only.")
    usd_amount = amount * DEMO_RATES_TO_USD[source]
    rate = DEMO_RATES_TO_USD[source] / DEMO_RATES_TO_USD[target]
    converted = usd_amount / DEMO_RATES_TO_USD[target]
    return round(converted, 4), round(rate, 6)


def _live_convert(amount: float, source: str, target: str, api_key: str) -> tuple[float, float]:
    payload = get_json(f"https://v6.exchangerate-api.com/v6/{api_key}/pair/{source}/{target}/{amount}")
    result = payload.get("result")
    if result == "error" or payload.get("conversion_result") is None:
        error = payload.get("error-type") or "The currency API could not complete the conversion."
        raise ValueError(str(error))
    converted = float(payload["conversion_result"])
    rate = float(payload.get("conversion_rate") or converted / amount)
    return round(converted, 4), round(rate, 6)


def execute(amount: float, from_currency: str, to_currency: str) -> dict[str, Any]:
    try:
        numeric = float(amount)
        if numeric < 0:
            raise ValueError("Amount cannot be negative.")
        source = _code(from_currency)
        target = _code(to_currency)
    except (TypeError, ValueError) as exc:
        return {"success": False, "error": str(exc), "summary": str(exc), "data": {}}

    api_key = getattr(settings, "CURRENCY_API_KEY", "") or ""
    try:
        if api_key:
            converted, rate = _live_convert(numeric, source, target, api_key)
            mode = "live"
            disclaimer = None
        else:
            converted, rate = _demo_convert(numeric, source, target)
            mode = "demo"
            disclaimer = DEMO_MODE_LABEL
    except (HttpError, ValueError) as exc:
        return {"success": False, "error": str(exc), "summary": str(exc), "data": {}}

    summary = f"{numeric} {source} = {converted} {target}"
    if mode == "demo":
        summary = f"{summary} ({DEMO_MODE_LABEL})"
    return {
        "success": True,
        "error": None,
        "summary": summary,
        "data": {
            "amount": numeric,
            "from_currency": source,
            "to_currency": target,
            "result": converted,
            "rate": rate,
            "mode": mode,
            "disclaimer": disclaimer,
        },
    }
