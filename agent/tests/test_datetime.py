from datetime import date

from django.test import SimpleTestCase

from agent.tools.datetime_tool import execute


class DateTimeToolTests(SimpleTestCase):
    def test_tokyo_timezone(self):
        result = execute(timezone="Asia/Tokyo")
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["timezone"], "Asia/Tokyo")
        self.assertIn("day_of_week", result["data"])

    def test_days_between(self):
        result = execute(start_date="2026-01-01", end_date="2026-09-02")
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["days_between"], (date(2026, 9, 2) - date(2026, 1, 1)).days)

    def test_invalid_timezone(self):
        result = execute(timezone="Not/AZone")
        self.assertFalse(result["success"])

    def test_invalid_date(self):
        result = execute(start_date="02-09-2026", end_date="2026-09-03")
        self.assertFalse(result["success"])
