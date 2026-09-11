from django.test import SimpleTestCase

from agent.templatetags.agent_extras import format_agent_html, plain_preview


class AgentFormattingTests(SimpleTestCase):
    def test_bold_markdown_becomes_strong(self):
        html = format_agent_html("25 × 64 = **1,600**")
        self.assertIn("<strong>1,600</strong>", html)
        self.assertNotIn("**", html)

    def test_escapes_html(self):
        html = format_agent_html("<script>alert(1)</script> and **safe**")
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertIn("<strong>safe</strong>", html)

    def test_lists(self):
        html = format_agent_html("- Hyderabad\n- London")
        self.assertIn("<ul>", html)
        self.assertIn("<li>Hyderabad</li>", html)

    def test_plain_preview_strips_markers(self):
        preview = plain_preview("The answer is **1600** exactly.", 40)
        self.assertEqual(preview, "The answer is 1600 exactly.")
        self.assertNotIn("**", preview)
