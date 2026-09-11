from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from agent.models import Challenge
from agent.tools import currency, weather, web_search


class ErrorHandlingTests(TestCase):
    def test_invalid_city_without_key(self):
        with override_settings(OPENWEATHERMAP_API_KEY=""):
            result = weather.execute("Hyderabad")
        self.assertFalse(result["success"])
        self.assertIn("not configured", result["error"].lower())

    def test_search_without_key(self):
        with override_settings(SERPAPI_API_KEY=""):
            result = web_search.execute("Python")
        self.assertFalse(result["success"])

    def test_currency_demo_mode_is_labelled(self):
        with override_settings(CURRENCY_API_KEY=""):
            result = currency.execute(100, "USD", "INR")
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["mode"], "demo")
        self.assertIn("DEMO MODE", result["summary"])
        self.assertIn("not live", result["data"]["disclaimer"].lower())

    @patch("agent.tools.weather.get_json")
    def test_invalid_city_from_api(self, mock_get):
        from agent.services.http_client import HttpError

        mock_get.side_effect = HttpError("missing", status_code=404)
        with override_settings(OPENWEATHERMAP_API_KEY="dummy"):
            result = weather.execute("NotACityXYZ")
        self.assertFalse(result["success"])
        self.assertIn("valid city", result["error"].lower())


class ViewSmokeTests(TestCase):
    def setUp(self):
        Challenge.objects.create(
            title="Sample",
            description="desc",
            difficulty=Challenge.BEGINNER,
            expected_tools=["calculator"],
            points=100,
            order=1,
        )

    def test_core_pages_render(self):
        names = [
            "dashboard",
            "tools",
            "playground",
            "agent_playground",
            "tasks",
            "activity",
            "history",
            "settings",
            "learning",
            "developer",
            "add_tool",
        ]
        for name in names:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)

    def test_dashboard_rejects_empty_query(self):
        response = self.client.post(reverse("dashboard"), {"query": " "})
        self.assertEqual(response.status_code, 200)

    def test_playground_calculator(self):
        response = self.client.post(
            reverse("playground"),
            {"tool": "calculator", "input_data": "25 * 64"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1600")

    def test_no_javascript_in_templates_or_static(self):
        roots = [Path(settings.BASE_DIR) / "templates", Path(settings.BASE_DIR) / "static"]
        extra_script_hits = []
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in {".html", ".css"}:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore").lower()
                if "xmlhttprequest" in text or "fetch(" in text:
                    extra_script_hits.append(str(path))
        self.assertEqual(extra_script_hits, [])
        js_path = Path(settings.BASE_DIR) / "static" / "js" / "agentlab.js"
        self.assertTrue(js_path.exists())
