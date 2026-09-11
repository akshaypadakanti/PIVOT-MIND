from django.test import SimpleTestCase

from agent.tools.calculator import CalculatorError, evaluate_expression, execute


class CalculatorTests(SimpleTestCase):
    def test_multiply(self):
        self.assertEqual(evaluate_expression("25 * 64"), 1600)

    def test_percentage_of(self):
        self.assertEqual(evaluate_expression("18% of 750"), 135)

    def test_division(self):
        self.assertEqual(evaluate_expression("15000 / 12"), 1250)

    def test_compound_interest_expression(self):
        result = evaluate_expression("10000 * (1 + 0.08)**3")
        self.assertAlmostEqual(float(result), 12597.12, places=2)

    def test_rejects_empty(self):
        with self.assertRaises(CalculatorError):
            evaluate_expression("   ")

    def test_rejects_names(self):
        with self.assertRaises(CalculatorError):
            evaluate_expression("__import__('os')")

    def test_rejects_attribute_access(self):
        with self.assertRaises(CalculatorError):
            evaluate_expression("(1).real")

    def test_division_by_zero(self):
        result = execute("10 / 0")
        self.assertFalse(result["success"])
        self.assertIn("zero", result["error"].lower())

    def test_execute_success(self):
        result = execute("2 + 2")
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["result"], 4)
