"""Score challenge attempts from observed tool usage and execution outcome."""
from __future__ import annotations

from agent.models import AgentExecution, Challenge, ChallengeAttempt


def evaluate_challenge(challenge: Challenge, execution: AgentExecution, query: str) -> ChallengeAttempt:
    expected = [str(name) for name in (challenge.expected_tools or [])]
    expected_set = set(expected)
    actual = [item.tool_name for item in execution.tool_executions.all()]
    actual_set = set(actual)

    feedback_parts: list[str] = []

    if not expected_set:
        selection_score = 30 if actual else 15
        feedback_parts.append("No expected tools were defined for this challenge.")
    elif expected_set == actual_set:
        selection_score = 30
        feedback_parts.append("Correct tool selection.")
    elif expected_set & actual_set:
        selection_score = round(30 * len(expected_set & actual_set) / len(expected_set))
        missing = expected_set - actual_set
        extra = actual_set - expected_set
        if missing:
            feedback_parts.append(f"Missing expected tool(s): {', '.join(sorted(missing))}.")
        if extra:
            feedback_parts.append(f"Unexpected extra tool(s): {', '.join(sorted(extra))}.")
    else:
        selection_score = 0
        feedback_parts.append(
            f"Expected tool(s): {', '.join(expected) or 'none'}. "
            f"The agent used: {', '.join(actual) or 'none'}."
        )

    successful_calls = [item for item in execution.tool_executions.all() if item.status == "success"]
    if execution.tool_executions.exists() and len(successful_calls) == execution.tool_executions.count():
        arguments_score = 20
        execution_score = 20
        feedback_parts.append("All tool calls executed successfully with usable arguments.")
    elif successful_calls:
        arguments_score = 10
        execution_score = 10
        feedback_parts.append("Some tool calls failed. Check arguments and API configuration.")
    elif execution.status == AgentExecution.STATUS_SUCCESS and not actual:
        # The model answered without tools. That can still be a failed challenge.
        arguments_score = 0
        execution_score = 0
        feedback_parts.append("The agent did not use tools for this challenge.")
    else:
        arguments_score = 0
        execution_score = 0
        feedback_parts.append("Tool execution did not succeed.")

    has_answer = bool((execution.final_response or "").strip()) and execution.status == AgentExecution.STATUS_SUCCESS
    if has_answer:
        answer_score = 20
        feedback_parts.append("A final answer was produced.")
    else:
        answer_score = 0
        feedback_parts.append("No successful final answer was produced.")

    extra_count = len(actual_set - expected_set) if expected_set else 0
    if not actual and expected_set:
        efficiency_score = 0
        feedback_parts.append("No tools were used, so efficiency could not be rewarded.")
    elif extra_count == 0 and actual:
        efficiency_score = 10
        feedback_parts.append("Tool usage was efficient.")
    elif extra_count == 1:
        efficiency_score = 5
        feedback_parts.append("One extra tool was used beyond the expected set.")
    else:
        efficiency_score = 0
        feedback_parts.append("Unnecessary extra tools reduced the efficiency score.")

    # Reward matching the expected number of tools when duplicates are expected (e.g. three weather calls).
    if expected:
        expected_count = len(expected)
        actual_count = len(actual)
        if actual_count < expected_count and selection_score > 0:
            feedback_parts.append(
                f"This challenge expected about {expected_count} tool call(s); the agent made {actual_count}."
            )

    total = selection_score + arguments_score + execution_score + answer_score + efficiency_score
    total = max(0, min(100, total))
    success = total >= 70 and execution.status == AgentExecution.STATUS_SUCCESS

    breakdown = {
        "tool_selection": selection_score,
        "arguments": arguments_score,
        "execution": execution_score,
        "final_answer": answer_score,
        "efficiency": efficiency_score,
        "total": total,
    }

    return ChallengeAttempt.objects.create(
        challenge=challenge,
        submitted_query=query,
        selected_tools=actual,
        score=total,
        success=success,
        feedback=" ".join(feedback_parts),
        breakdown=breakdown,
        agent_execution=execution,
    )
