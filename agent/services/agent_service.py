"""
Gemini-powered multi-tool agent.

Routing is performed by Gemini function calling (Interactions API),
not a giant if/elif chain.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings

from agent.models import AgentExecution, ToolExecution
from agent.services import tool_registry

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are AgentLab, an educational AI agent that solves user questions by choosing tools.

Rules:
- Use tools whenever they improve accuracy. Do not guess live weather, web facts, or current events.
- Prefer calculator for math. Convert natural-language math into a numeric expression.
- Prefer weather for current conditions in a city.
- Prefer web_search for news, current people, versions, and changing facts.
- Prefer knowledge_search for encyclopedic background.
- Prefer unit_converter for unit changes, including converting weather temperatures.
- Prefer get_datetime for dates, times, timezones, weekdays, and day counts.
- Prefer currency_converter for money conversions. Demo rates are not live — say so if the tool result is demo.
- Prefer analyze_text for counting words/sentences in supplied text.
- Prefer validate_json for checking JSON.
- You may call multiple tools, including the same tool more than once (for example two cities).
- Chain tools when needed: weather then unit_converter, search then calculator, currency then calculator.
- Never reveal hidden chain-of-thought. After tools finish, write a clear, useful final answer.
- If a tool is not configured, explain that honestly and still help with whatever you can.

Final answer style:
- Write in short, complete sentences a student can read at a glance.
- Use **bold** only for the key result (the number, converted value, city, or conclusion).
- Use a short bullet list when comparing two or more items.
- Do not use headings, tables, JSON dumps, or nested markdown.
- Do not wrap the whole answer in asterisks.
- Prefer one or two short paragraphs, then the result.
"""

DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"


class AgentRunError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.user_message = message


@dataclass
class ModelFunctionCall:
    name: str
    arguments: dict[str, Any]
    call_id: str = ""


@dataclass
class ModelTurn:
    text: str = ""
    function_calls: list[ModelFunctionCall] = field(default_factory=list)
    interaction_id: str | None = None


def _require_gemini_key() -> str:
    api_key = getattr(settings, "GEMINI_API_KEY", "") or ""
    if not api_key:
        raise AgentRunError(
            "Gemini is not configured. Add GEMINI_API_KEY to your .env file to run the agent."
        )
    return api_key


def _gemini_client(api_key: str):
    from google import genai
    from google.genai import types

    timeout_seconds = max(int(getattr(settings, "AGENT_API_TIMEOUT", 12)), 1)
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=timeout_seconds * 1000),
    )


def _friendly_gemini_error(exc: Exception) -> str:
    name = exc.__class__.__name__
    text = str(exc).lower()
    if "timeout" in name.lower() or "timeout" in text or "deadline" in text:
        return "The language model timed out. Please try again."
    if "rate" in text or "429" in text or "resource exhausted" in text:
        return "The language model is rate-limited right now. Please wait and try again."
    if "404" in text or "not_found" in text or "no longer available" in text:
        return (
            "The configured Gemini model is not available. "
            f"Set GEMINI_MODEL={DEFAULT_GEMINI_MODEL} in your .env file and restart the server."
        )
    if (
        "api key" in text
        or "api_key" in text
        or "401" in text
        or "403" in text
        or "permission" in text
        or "unauthenticated" in text
        or ("invalid argument" in text and "key" in text)
    ):
        return "The Gemini API key was rejected. Check GEMINI_API_KEY in your .env file."
    if "connection" in text or "network" in text:
        return "Could not reach Gemini. Check your network connection."
    return "The language model could not complete this request. Please try again."


def _tool_payload(result: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "success": result.get("success"),
        "summary": result.get("summary"),
        "error": result.get("error"),
        "data": result.get("data") or {},
    }
    serialized = json.dumps(payload, ensure_ascii=False, default=str)
    if len(serialized) > 8000:
        payload["data"] = {"truncated": True}
        serialized = json.dumps(payload, ensure_ascii=False, default=str)
    return json.loads(serialized)


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    try:
        return dict(value)
    except (TypeError, ValueError):
        return {}


def _function_result_step(name: str, call_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function_result",
        "name": name,
        "call_id": call_id or name,
        "result": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, default=str)}],
    }


def _parse_interaction(interaction: Any) -> ModelTurn:
    calls: list[ModelFunctionCall] = []
    steps = getattr(interaction, "steps", None) or []
    for step in steps:
        if getattr(step, "type", None) != "function_call":
            continue
        calls.append(
            ModelFunctionCall(
                name=getattr(step, "name", "") or "",
                arguments=_as_dict(getattr(step, "arguments", None)),
                call_id=str(getattr(step, "id", "") or ""),
            )
        )
    text = (getattr(interaction, "output_text", None) or "").strip()
    return ModelTurn(
        text=text,
        function_calls=calls,
        interaction_id=getattr(interaction, "id", None),
    )


def _generate_model_turn(user_input: Any, previous_id: str | None = None) -> ModelTurn:
    api_key = _require_gemini_key()
    client = _gemini_client(api_key)
    model = getattr(settings, "GEMINI_MODEL", DEFAULT_GEMINI_MODEL) or DEFAULT_GEMINI_MODEL
    timeout_seconds = max(int(getattr(settings, "AGENT_API_TIMEOUT", 12)), 1)
    kwargs: dict[str, Any] = {
        "model": model,
        "input": user_input,
        "tools": tool_registry.gemini_tools(),
        "system_instruction": SYSTEM_PROMPT,
        "timeout": float(timeout_seconds),
    }
    if previous_id:
        kwargs["previous_interaction_id"] = previous_id

    try:
        interaction = client.interactions.create(**kwargs)
    except Exception as exc:
        logger.exception("Gemini interactions.create failed")
        raise AgentRunError(_friendly_gemini_error(exc)) from exc

    return _parse_interaction(interaction)


def run_agent(user_query: str) -> AgentExecution:
    started = time.perf_counter()
    execution = AgentExecution.objects.create(
        user_query=user_query,
        status=AgentExecution.STATUS_PENDING,
    )
    max_calls = max(1, int(getattr(settings, "AGENT_MAX_TOOL_CALLS", 8)))

    try:
        _require_gemini_key()
        tool_calls_used = 0
        final_text = ""
        previous_id: str | None = None
        pending_input: Any = user_query

        while True:
            turn = _generate_model_turn(pending_input, previous_id)
            if turn.interaction_id:
                previous_id = turn.interaction_id

            if not turn.function_calls:
                final_text = turn.text
                break

            function_results: list[dict[str, Any]] = []
            for call in turn.function_calls:
                if tool_calls_used >= max_calls:
                    payload = {
                        "success": False,
                        "error": f"Maximum tool-call limit of {max_calls} was reached.",
                        "summary": "Tool-call limit reached.",
                        "data": {},
                    }
                    function_results.append(_function_result_step(call.name, call.call_id, payload))
                    continue

                tool_calls_used += 1
                arguments = call.arguments if isinstance(call.arguments, dict) else {}
                call_started = time.perf_counter()
                result = tool_registry.execute_tool(call.name, arguments)
                elapsed = time.perf_counter() - call_started
                ToolExecution.objects.create(
                    agent_execution=execution,
                    tool_name=call.name,
                    arguments=arguments,
                    result_summary=(result.get("summary") or "")[:2000],
                    status=ToolExecution.STATUS_SUCCESS
                    if result.get("success")
                    else ToolExecution.STATUS_FAILED,
                    execution_time=round(elapsed, 4),
                )
                function_results.append(
                    _function_result_step(call.name, call.call_id, _tool_payload(result))
                )

            pending_input = function_results
            if tool_calls_used >= max_calls:
                pending_input = function_results + [
                    {
                        "type": "text",
                        "text": (
                            "The maximum number of tool calls has been reached. "
                            "Produce the best final answer you can with the tool results so far."
                        ),
                    }
                ]

        if not final_text:
            final_text = "The agent finished but did not return a final answer."

        execution.final_response = final_text
        execution.status = AgentExecution.STATUS_SUCCESS
        execution.tool_call_count = tool_calls_used
        execution.execution_time = round(time.perf_counter() - started, 4)
        execution.save()
        return execution

    except AgentRunError as exc:
        execution.final_response = exc.user_message
        execution.status = AgentExecution.STATUS_FAILED
        execution.tool_call_count = execution.tool_executions.count()
        execution.execution_time = round(time.perf_counter() - started, 4)
        execution.save()
        return execution
    except Exception:
        logger.exception("Unexpected agent failure")
        execution.final_response = "The agent encountered an unexpected error. Please try again."
        execution.status = AgentExecution.STATUS_FAILED
        execution.tool_call_count = execution.tool_executions.count()
        execution.execution_time = round(time.perf_counter() - started, 4)
        execution.save()
        return execution
