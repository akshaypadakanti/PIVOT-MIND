from django.test import SimpleTestCase

from agent.tools.unit_converter import execute


class UnitConverterTests(SimpleTestCase):
    def test_km_to_miles(self):
        result = execute(10, "km", "miles")
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["data"]["result"], 6.21371192, places=5)

    def test_celsius_to_fahrenheit(self):
        result = execute(0, "C", "F")
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["result"], 32)

    def test_kg_to_pounds(self):
        result = execute(1, "kg", "pounds")
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["data"]["result"], 2.20462262, places=5)

    def test_incompatible_units(self):
        result = execute(1, "km", "kg")
        self.assertFalse(result["success"])

    def test_invalid_value(self):
        result = execute("abc", "km", "miles")
        self.assertFalse(result["success"])
