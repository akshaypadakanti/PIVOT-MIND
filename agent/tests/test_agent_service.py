from unittest.mock import patch

from django.test import TestCase, override_settings

from agent.models import AgentExecution, ToolExecution
from agent.services import agent_service
from agent.services.agent_service import ModelFunctionCall, ModelTurn


class AgentServiceTests(TestCase):
    @override_settings(GEMINI_API_KEY="")
    def test_missing_gemini_key(self):
        execution = agent_service.run_agent("Calculate 2 + 2")
        self.assertEqual(execution.status, AgentExecution.STATUS_FAILED)
        self.assertIn("not configured", execution.final_response.lower())

    @override_settings(GEMINI_API_KEY="test-key", AGENT_MAX_TOOL_CALLS=4)
    @patch("agent.services.agent_service._generate_model_turn")
    def test_single_tool_then_final_answer(self, mock_turn):
        mock_turn.side_effect = [
            ModelTurn(
                function_calls=[
                    ModelFunctionCall(name="calculator", arguments={"expression": "25 * 64"})
                ]
            ),
            ModelTurn(text="25 × 64 is 1600."),
        ]
        execution = agent_service.run_agent("Calculate 25 × 64")
        self.assertEqual(execution.status, AgentExecution.STATUS_SUCCESS)
        self.assertEqual(execution.tool_call_count, 1)
        self.assertIn("1600", execution.final_response)
        step = execution.tool_executions.get()
        self.assertEqual(step.tool_name, "calculator")
        self.assertEqual(step.status, ToolExecution.STATUS_SUCCESS)

    @override_settings(GEMINI_API_KEY="test-key", AGENT_MAX_TOOL_CALLS=8)
    @patch("agent.services.agent_service._generate_model_turn")
    def test_multi_tool_chaining(self, mock_turn):
        mock_turn.side_effect = [
            ModelTurn(
                function_calls=[
                    ModelFunctionCall(name="calculator", arguments={"expression": "100 * 0.18"}),
                    ModelFunctionCall(
                        name="unit_converter",
                        arguments={"value": 10, "from_unit": "km", "to_unit": "miles"},
                    ),
                ]
            ),
            ModelTurn(text="GST is 18 and 10 km is about 6.21 miles."),
        ]
        execution = agent_service.run_agent("Calculate 18% of 100 and convert 10 km to miles")
        self.assertEqual(execution.status, AgentExecution.STATUS_SUCCESS)
        self.assertEqual(execution.tool_call_count, 2)
        names = list(execution.tool_executions.values_list("tool_name", flat=True))
        self.assertEqual(names, ["calculator", "unit_converter"])

    @override_settings(GEMINI_API_KEY="test-key", AGENT_API_TIMEOUT=15)
    def test_client_timeout_setting(self):
        client = agent_service._gemini_client("test-key")
        self.assertIsNotNone(client)

