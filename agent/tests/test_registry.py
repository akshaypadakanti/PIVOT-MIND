from django.test import SimpleTestCase, override_settings

from agent.services import tool_registry


class ToolRegistryTests(SimpleTestCase):
    def test_all_expected_tools_registered(self):
        names = {tool.name for tool in tool_registry.list_tools()}
        expected = {
            "calculator",
            "web_search",
            "weather",
            "unit_converter",
            "get_datetime",
            "currency_converter",
            "analyze_text",
            "validate_json",
            "knowledge_search",
        }
        self.assertEqual(names, expected)

    def test_gemini_declarations_have_name_and_parameters(self):
        for declaration in tool_registry.gemini_tools():
            self.assertIn("name", declaration)
            self.assertIn("parameters", declaration)
            self.assertEqual(declaration["parameters"].get("type"), "object")

    def test_validate_arguments_missing(self):
        tool = tool_registry.get_tool("calculator")
        ok, message = tool_registry.validate_arguments(tool, {})
        self.assertFalse(ok)
        self.assertIn("expression", message)

    def test_validate_arguments_ok(self):
        tool = tool_registry.get_tool("weather")
        ok, message = tool_registry.validate_arguments(tool, {"city": "Hyderabad"})
        self.assertTrue(ok)
        self.assertEqual(message, "")

    def test_unknown_tool(self):
        result = tool_registry.execute_tool("not_a_tool", {})
        self.assertFalse(result["success"])

    def test_playground_parser_for_units(self):
        tool = tool_registry.get_tool("unit_converter")
        args = tool_registry.parse_playground_input(tool, "10 km to miles")
        self.assertEqual(args["from_unit"].lower(), "km")
        self.assertEqual(args["value"], 10)

    @override_settings(SERPAPI_API_KEY="", OPENWEATHERMAP_API_KEY="")
    def test_external_tools_unconfigured(self):
        weather = tool_registry.execute_tool("weather", {"city": "Hyderabad"})
        search = tool_registry.execute_tool("web_search", {"query": "Django"})
        self.assertFalse(weather["success"])
        self.assertFalse(search["success"])
        self.assertIn("not configured", weather["error"].lower())
        self.assertIn("not configured", search["error"].lower())

    def test_unexpected_tool_arguments(self):
        result = tool_registry.execute_tool("calculator", {"expression": "2+2", "extra_arg": "invalid"})
        self.assertFalse(result["success"])
        self.assertEqual(result["summary"], "Invalid tool arguments.")

