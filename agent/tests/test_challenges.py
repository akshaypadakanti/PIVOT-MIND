from django.test import TestCase

from agent.models import AgentExecution, Challenge, ToolExecution
from agent.services.challenge_evaluator import evaluate_challenge


class ChallengeEvaluationTests(TestCase):
    def setUp(self):
        self.challenge = Challenge.objects.create(
            title="Percent of 750",
            description="Calculate 18% of 750",
            difficulty=Challenge.BEGINNER,
            expected_tools=["calculator"],
            points=100,
            sample_query="What is 18% of 750?",
            order=99,
        )

    def test_perfect_calculator_run(self):
        execution = AgentExecution.objects.create(
            user_query="What is 18% of 750?",
            final_response="18% of 750 is 135.",
            status=AgentExecution.STATUS_SUCCESS,
            tool_call_count=1,
            execution_time=0.2,
        )
        ToolExecution.objects.create(
            agent_execution=execution,
            tool_name="calculator",
            arguments={"expression": "(18/100)*750"},
            result_summary="135",
            status=ToolExecution.STATUS_SUCCESS,
            execution_time=0.01,
        )
        attempt = evaluate_challenge(self.challenge, execution, execution.user_query)
        self.assertEqual(attempt.score, 100)
        self.assertTrue(attempt.success)
        self.assertEqual(attempt.breakdown["tool_selection"], 30)
        self.assertEqual(attempt.breakdown["efficiency"], 10)

    def test_wrong_tool_low_score(self):
        execution = AgentExecution.objects.create(
            user_query="What is 18% of 750?",
            final_response="I looked it up.",
            status=AgentExecution.STATUS_SUCCESS,
            tool_call_count=1,
            execution_time=0.2,
        )
        ToolExecution.objects.create(
            agent_execution=execution,
            tool_name="web_search",
            arguments={"query": "18% of 750"},
            result_summary="unrelated",
            status=ToolExecution.STATUS_SUCCESS,
            execution_time=0.01,
        )
        attempt = evaluate_challenge(self.challenge, execution, execution.user_query)
        self.assertEqual(attempt.breakdown["tool_selection"], 0)
        self.assertLess(attempt.score, 70)
        self.assertFalse(attempt.success)
