"""Unit converter for length, mass, volume, and temperature."""
from __future__ import annotations

from typing import Any

NAME = "unit_converter"
CATEGORY = "Local"
DESCRIPTION = "Converts length, mass, volume, and temperature between common units."
REQUIRES_API_KEY = None
EXAMPLES = [
    "Convert 10 km to miles",
    "Convert 25 Celsius to Fahrenheit",
    "How many pounds is 70 kg?",
    "Convert 5 liters to gallons",
]

_ALIASES = {
    "kilometer": "km",
    "kilometers": "km",
    "km": "km",
    "meter": "m",
    "meters": "m",
    "m": "m",
    "mile": "mi",
    "miles": "mi",
    "mi": "mi",
    "foot": "ft",
    "feet": "ft",
    "ft": "ft",
    "kilogram": "kg",
    "kilograms": "kg",
    "kg": "kg",
    "pound": "lb",
    "pounds": "lb",
    "lb": "lb",
    "lbs": "lb",
    "celsius": "c",
    "centigrade": "c",
    "c": "c",
    "fahrenheit": "f",
    "f": "f",
    "liter": "l",
    "liters": "l",
    "litre": "l",
    "litres": "l",
    "l": "l",
    "gallon": "gal",
    "gallons": "gal",
    "gal": "gal",
}

_LENGTH_TO_M = {"km": 1000.0, "m": 1.0, "mi": 1609.344, "ft": 0.3048}
_MASS_TO_KG = {"kg": 1.0, "lb": 0.45359237}
_VOLUME_TO_L = {"l": 1.0, "gal": 3.785411784}
_TEMP = {"c", "f"}

SCHEMA = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "Convert a numeric value from one unit to another. "
            "Supported: km/miles, meters/feet, kg/pounds, Celsius/Fahrenheit, liters/gallons."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "value": {"type": "number", "description": "The numeric value to convert."},
                "from_unit": {
                    "type": "string",
                    "description": "Source unit, for example km, miles, kg, C, F, liters.",
                },
                "to_unit": {
                    "type": "string",
                    "description": "Target unit, for example miles, feet, pounds, F, gallons.",
                },
            },
            "required": ["value", "from_unit", "to_unit"],
        },
    },
}


def _normalize_unit(unit: str) -> str:
    key = (unit or "").strip().lower().replace("°", "")
    if key not in _ALIASES:
        raise ValueError(f"Unsupported unit '{unit}'.")
    return _ALIASES[key]


def _convert(value: float, from_unit: str, to_unit: str) -> float:
    source = _normalize_unit(from_unit)
    target = _normalize_unit(to_unit)
    if source == target:
        return float(value)

    if source in _TEMP or target in _TEMP:
        if source not in _TEMP or target not in _TEMP:
            raise ValueError("Temperature can only be converted between Celsius and Fahrenheit.")
        if source == "c" and target == "f":
            return (value * 9 / 5) + 32
        return (value - 32) * 5 / 9

    tables = (_LENGTH_TO_M, _MASS_TO_KG, _VOLUME_TO_L)
    for table in tables:
        if source in table and target in table:
            base = value * table[source]
            return base / table[target]
    raise ValueError(f"Cannot convert {from_unit} to {to_unit}. Units must belong to the same category.")


def execute(value: float, from_unit: str, to_unit: str) -> dict[str, Any]:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return {
            "success": False,
            "error": "Value must be a number.",
            "summary": "Invalid numeric value.",
            "data": {},
        }
    try:
        result = round(_convert(numeric, from_unit, to_unit), 8)
    except ValueError as exc:
        return {"success": False, "error": str(exc), "summary": str(exc), "data": {}}

    summary = f"{numeric} {from_unit} = {result} {to_unit}"
    return {
        "success": True,
        "error": None,
        "summary": summary,
        "data": {
            "value": numeric,
            "from_unit": from_unit,
            "to_unit": to_unit,
            "result": result,
        },
    }
