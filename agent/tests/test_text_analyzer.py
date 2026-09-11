from django.test import SimpleTestCase

from agent.tools.text_analyzer import execute


class TextAnalyzerTests(SimpleTestCase):
    def test_counts(self):
        text = "Hello world. This is AgentLab.\n\nA second paragraph!"
        result = execute(text)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["words"], 8)
        self.assertEqual(result["data"]["sentences"], 3)
        self.assertEqual(result["data"]["paragraphs"], 2)
        self.assertGreater(result["data"]["characters"], 0)

    def test_empty(self):
        result = execute("   ")
        self.assertFalse(result["success"])
