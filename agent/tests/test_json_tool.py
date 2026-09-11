from django.test import SimpleTestCase

from agent.tools.json_tool import execute


class JsonToolTests(SimpleTestCase):
    def test_valid_object(self):
        result = execute('{"name": "AgentLab", "tools": 9}')
        self.assertTrue(result["success"])
        self.assertTrue(result["data"]["valid"])
        self.assertEqual(result["data"]["top_level_keys"], 2)
        self.assertIn("name", result["data"]["keys"])

    def test_invalid_json(self):
        result = execute("{name: nope}")
        self.assertTrue(result["success"])
        self.assertFalse(result["data"]["valid"])

    def test_empty(self):
        result = execute("")
        self.assertFalse(result["success"])
