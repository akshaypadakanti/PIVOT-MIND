"""JSON validation and pretty-printing using the standard library json module."""
from __future__ import annotations

import json
from typing import Any

NAME = "validate_json"
CATEGORY = "Local"
DESCRIPTION = "Validates JSON, pretty-prints it, and reports basic structure information."
REQUIRES_API_KEY = None
EXAMPLES = [
    'Validate this JSON: {"name": "AgentLab", "tools": 9}',
    "Is this JSON valid: [1, 2, 3]?",
    'Pretty-print {"a":1,"b":{"c":true}}',
]

SCHEMA = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": "Validate a JSON string. If valid, pretty-print it and describe its top-level structure.",
        "parameters": {
            "type": "object",
            "properties": {
                "json_text": {"type": "string", "description": "Raw JSON text to validate."},
            },
            "required": ["json_text"],
        },
    },
}


def _structure(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {
            "type": "object",
            "top_level_keys": len(value),
            "keys": list(value.keys()),
        }
    if isinstance(value, list):
        return {
            "type": "array",
            "top_level_keys": 0,
            "length": len(value),
        }
    return {
        "type": type(value).__name__,
        "top_level_keys": 0,
    }


def execute(json_text: str) -> dict[str, Any]:
    raw = json_text if json_text is not None else ""
    if not str(raw).strip():
        return {
            "success": False,
            "error": "Please provide JSON text to validate.",
            "summary": "Missing JSON text.",
            "data": {"valid": False},
        }
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        message = f"Invalid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})."
        return {
            "success": True,
            "error": None,
            "summary": message,
            "data": {"valid": False, "error": message},
        }

    pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
    info = _structure(parsed)
    summary = f"Valid JSON ({info['type']}, {info.get('top_level_keys', 0)} top-level keys)."
    return {
        "success": True,
        "error": None,
        "summary": summary,
        "data": {
            "valid": True,
            "pretty": pretty,
            **info,
        },
    }
