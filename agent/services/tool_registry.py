"""Central tool registry. Adding a tool means creating a module and listing it here."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from django.conf import settings

from agent.tools import (
    calculator,
    currency,
    datetime_tool,
    json_tool,
    knowledge_search,
    text_analyzer,
    unit_converter,
    weather,
    web_search,
)


@dataclass
class ToolDefinition:
    name: str
    description: str
    category: str
    execute: Callable[..., dict[str, Any]]
    schema: dict[str, Any]
    examples: list[str] = field(default_factory=list)
    requires_api_key: str | None = None
    availability_label: str = ""

    @property
    def is_local(self) -> bool:
        return self.category == "Local"

    @property
    def configured(self) -> bool:
        if not self.requires_api_key:
            return True
        return bool(getattr(settings, self.requires_api_key, "") or "")

    @property
    def status_label(self) -> str:
        if self.availability_label:
            return self.availability_label
        if not self.requires_api_key:
            return "Ready"
        return "Configured" if self.configured else "Not Configured"

    @property
    def type_label(self) -> str:
        if self.category == "Local":
            return "Local"
        if self.category == "Public API":
            return "Public API"
        return "External API"

    @property
    def primary_parameter(self) -> str | None:
        props = ((self.schema.get("function") or {}).get("parameters") or {}).get("properties") or {}
        required = ((self.schema.get("function") or {}).get("parameters") or {}).get("required") or []
        if required:
            return required[0]
        if len(props) == 1:
            return next(iter(props))
        return None

    def function_schema(self) -> dict[str, Any]:
        return self.schema

    def gemini_declaration(self) -> dict[str, Any]:
        function = self.schema.get("function") or {}
        return {
            "type": "function",
            "name": function.get("name") or self.name,
            "description": function.get("description") or self.description,
            "parameters": function.get("parameters")
            or {"type": "object", "properties": {}},
        }


_TOOL_MODULES = [
    calculator,
    web_search,
    weather,
    unit_converter,
    datetime_tool,
    currency,
    text_analyzer,
    json_tool,
    knowledge_search,
]


def _build_registry() -> dict[str, ToolDefinition]:
    registry: dict[str, ToolDefinition] = {}
    for module in _TOOL_MODULES:
        extra_label = ""
        if module.NAME == "currency_converter" and not (getattr(settings, "CURRENCY_API_KEY", "") or ""):
            extra_label = "Demo Mode"
        tool = ToolDefinition(
            name=module.NAME,
            description=module.DESCRIPTION,
            category=module.CATEGORY,
            execute=module.execute,
            schema=module.SCHEMA,
            examples=list(getattr(module, "EXAMPLES", [])),
            requires_api_key=getattr(module, "REQUIRES_API_KEY", None),
            availability_label=extra_label,
        )
        registry[tool.name] = tool
    return registry


def get_registry() -> dict[str, ToolDefinition]:
    return _build_registry()


def get_tool(name: str) -> ToolDefinition | None:
    return get_registry().get(name)


def list_tools() -> list[ToolDefinition]:
    return list(get_registry().values())


def gemini_tools() -> list[dict[str, Any]]:
    return [tool.gemini_declaration() for tool in list_tools()]


def required_fields(tool: ToolDefinition) -> list[str]:
    params = (tool.schema.get("function") or {}).get("parameters") or {}
    return list(params.get("required") or [])


def validate_arguments(tool: ToolDefinition, arguments: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(arguments, dict):
        return False, "Tool arguments must be a JSON object."
    missing = [field for field in required_fields(tool) if field not in arguments or arguments[field] in (None, "")]
    if missing:
        return False, f"Missing required argument(s): {', '.join(missing)}."
    return True, ""


def parse_playground_input(tool: ToolDefinition, raw: str) -> dict[str, Any]:
    """Map a single playground textarea to tool keyword arguments."""
    text = (raw or "").strip()
    if text:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            return parsed

    primary = tool.primary_parameter
    required = required_fields(tool)

    if tool.name == "unit_converter":
        return _parse_conversion_text(text)
    if tool.name == "currency_converter":
        return _parse_currency_text(text)
    if tool.name == "get_datetime":
        if not text:
            return {"timezone": "UTC"}
        if " to " in text.lower() or "," in text and text.count("-") >= 4:
            return _parse_date_range(text)
        return {"timezone": text}

    if len(required) <= 1 and primary:
        return {primary: text}
    if primary:
        return {primary: text}
    raise ValueError("This tool needs JSON arguments, for example {\"value\": 10, \"from_unit\": \"km\", \"to_unit\": \"miles\"}.")


def _parse_conversion_text(text: str) -> dict[str, Any]:
    import re

    match = re.search(
        r"(-?\d+(?:\.\d+)?)\s*([A-Za-z°]+)\s+(?:to|in)\s+([A-Za-z°]+)",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return {
            "value": float(match.group(1)),
            "from_unit": match.group(2),
            "to_unit": match.group(3),
        }
    raise ValueError("Use JSON or a phrase like '10 km to miles'.")


def _parse_currency_text(text: str) -> dict[str, Any]:
    import re

    match = re.search(
        r"(-?\d+(?:\.\d+)?)\s*([A-Za-z]{3})\s+(?:to|in)\s+([A-Za-z]{3})",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return {
            "amount": float(match.group(1)),
            "from_currency": match.group(2).upper(),
            "to_currency": match.group(3).upper(),
        }
    raise ValueError("Use JSON or a phrase like '100 USD to INR'.")


def _parse_date_range(text: str) -> dict[str, Any]:
    import re

    dates = re.findall(r"\d{4}-\d{2}-\d{2}", text)
    if len(dates) >= 2:
        return {"start_date": dates[0], "end_date": dates[1], "timezone": "UTC"}
    return {"timezone": text}


def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    tool = get_tool(name)
    if tool is None:
        return {
            "success": False,
            "error": f"Unknown tool '{name}'.",
            "summary": f"Unknown tool '{name}'.",
            "data": {},
        }
    ok, message = validate_arguments(tool, arguments)
    if not ok:
        return {"success": False, "error": message, "summary": message, "data": {}}
    import inspect
    try:
        sig = inspect.signature(tool.execute)
        sig.bind(**arguments)
    except TypeError:
        return {
            "success": False,
            "error": "The tool received unexpected arguments.",
            "summary": "Invalid tool arguments.",
            "data": {},
        }
    try:
        result = tool.execute(**arguments)
    except Exception:
        return {
            "success": False,
            "error": "The tool failed while running. Please check your input and try again.",
            "summary": "Tool execution failed.",
            "data": {},
        }
    if not isinstance(result, dict):
        return {
            "success": False,
            "error": "The tool returned an unexpected result.",
            "summary": "Unexpected tool result.",
            "data": {},
        }
    result.setdefault("success", False)
    result.setdefault("summary", "")
    result.setdefault("data", {})
    result.setdefault("error", None)
    return result
