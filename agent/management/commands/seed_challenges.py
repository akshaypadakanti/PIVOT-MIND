from __future__ import annotations

from django.core.management.base import BaseCommand

from agent.models import Challenge

CHALLENGES = [
    {
        "order": 1,
        "title": "Calculate 25 × 64",
        "description": "Ask the agent to multiply 25 by 64. The calculator tool should be selected.",
        "difficulty": Challenge.BEGINNER,
        "expected_tools": ["calculator"],
        "points": 100,
        "sample_query": "Calculate 25 × 64",
    },
    {
        "order": 2,
        "title": "Calculate 18% of 750",
        "description": "Have the agent compute 18 percent of 750 using the calculator.",
        "difficulty": Challenge.BEGINNER,
        "expected_tools": ["calculator"],
        "points": 100,
        "sample_query": "What is 18% of 750?",
    },
    {
        "order": 3,
        "title": "Weather in Hyderabad",
        "description": "Request the current weather in Hyderabad. Requires the weather tool.",
        "difficulty": Challenge.BEGINNER,
        "expected_tools": ["weather"],
        "points": 100,
        "sample_query": "What's the weather in Hyderabad?",
    },
    {
        "order": 4,
        "title": "Latest Python release",
        "description": "Search the web for the latest Python release.",
        "difficulty": Challenge.BEGINNER,
        "expected_tools": ["web_search"],
        "points": 100,
        "sample_query": "What is the latest Python version?",
    },
    {
        "order": 5,
        "title": "Convert 10 km to miles",
        "description": "Convert 10 kilometers to miles with the unit converter.",
        "difficulty": Challenge.BEGINNER,
        "expected_tools": ["unit_converter"],
        "points": 100,
        "sample_query": "Convert 10 km to miles",
    },
    {
        "order": 6,
        "title": "Current time in Tokyo",
        "description": "Find the current time in Tokyo using the date & time tool.",
        "difficulty": Challenge.BEGINNER,
        "expected_tools": ["get_datetime"],
        "points": 100,
        "sample_query": "What time is it in Tokyo?",
    },
    {
        "order": 7,
        "title": "Analyze a paragraph",
        "description": "Supply a short paragraph and ask the agent to analyze word and sentence counts.",
        "difficulty": Challenge.BEGINNER,
        "expected_tools": ["analyze_text"],
        "points": 100,
        "sample_query": "Analyze this paragraph: AgentLab teaches students how an AI agent chooses tools, executes them, and explains the result in plain language.",
    },
    {
        "order": 8,
        "title": "Validate a JSON object",
        "description": "Ask the agent to validate a JSON object and pretty-print it.",
        "difficulty": Challenge.BEGINNER,
        "expected_tools": ["validate_json"],
        "points": 100,
        "sample_query": 'Validate this JSON: {"name": "AgentLab", "tools": 9, "mode": "learning"}',
    },
    {
        "order": 9,
        "title": "Hyderabad temperature in Fahrenheit",
        "description": "Get Hyderabad weather, then convert the temperature to Fahrenheit.",
        "difficulty": Challenge.INTERMEDIATE,
        "expected_tools": ["weather", "unit_converter"],
        "points": 150,
        "sample_query": "What is the weather in Hyderabad and convert the temperature to Fahrenheit?",
    },
    {
        "order": 10,
        "title": "India's population, then 10%",
        "description": "Search for India's population and calculate 10% of that figure.",
        "difficulty": Challenge.INTERMEDIATE,
        "expected_tools": ["web_search", "calculator"],
        "points": 150,
        "sample_query": "Search for India's population and calculate 10% of it.",
    },
    {
        "order": 11,
        "title": "Compare Hyderabad and London temperatures",
        "description": "Fetch weather for both cities and report the temperature difference.",
        "difficulty": Challenge.INTERMEDIATE,
        "expected_tools": ["weather", "calculator"],
        "points": 150,
        "sample_query": "Get the temperature in London and Hyderabad and tell me the difference.",
    },
    {
        "order": 12,
        "title": "USD to INR plus 18% GST",
        "description": "Convert USD to INR, then calculate 18% GST on the converted amount.",
        "difficulty": Challenge.INTERMEDIATE,
        "expected_tools": ["currency_converter", "calculator"],
        "points": 150,
        "sample_query": "Convert 100 USD to INR and then calculate 18% GST on that amount.",
    },
    {
        "order": 13,
        "title": "Search and summarize a technology",
        "description": "Search for information about a technology and summarize the findings.",
        "difficulty": Challenge.INTERMEDIATE,
        "expected_tools": ["web_search"],
        "points": 150,
        "sample_query": "Search for Django REST framework and summarize what it is used for.",
    },
    {
        "order": 14,
        "title": "Days between two dates",
        "description": "Ask how many days exist between two specific dates.",
        "difficulty": Challenge.INTERMEDIATE,
        "expected_tools": ["get_datetime"],
        "points": 150,
        "sample_query": "How many days are there between 2026-01-01 and 2026-09-02?",
    },
    {
        "order": 15,
        "title": "Hottest of three cities",
        "description": "Get weather for three cities and identify which is hottest.",
        "difficulty": Challenge.ADVANCED,
        "expected_tools": ["weather"],
        "points": 200,
        "sample_query": "Get the weather in Hyderabad, London, and Tokyo, then tell me which city is hottest.",
    },
    {
        "order": 16,
        "title": "Population percentage difference",
        "description": "Search for two populations and calculate the percentage difference.",
        "difficulty": Challenge.ADVANCED,
        "expected_tools": ["web_search", "calculator"],
        "points": 200,
        "sample_query": "Search for the populations of India and the United States and calculate the percentage difference.",
    },
    {
        "order": 17,
        "title": "Current information plus calculation",
        "description": "Search for a current figure, then perform a calculation with that result.",
        "difficulty": Challenge.ADVANCED,
        "expected_tools": ["web_search", "calculator"],
        "points": 200,
        "sample_query": "Search for the current population of Tokyo and calculate how many people that is per square kilometer if the area is 2194 km².",
    },
    {
        "order": 18,
        "title": "Currency conversion then GST",
        "description": "Convert a currency amount, then calculate GST on the result.",
        "difficulty": Challenge.ADVANCED,
        "expected_tools": ["currency_converter", "calculator"],
        "points": 200,
        "sample_query": "Convert 250 EUR to USD and then calculate 18% GST on the converted amount.",
    },
    {
        "order": 19,
        "title": "Research plus calculation",
        "description": "Look up a factual figure with knowledge or web search, then calculate with it.",
        "difficulty": Challenge.ADVANCED,
        "expected_tools": ["knowledge_search", "calculator"],
        "points": 200,
        "sample_query": "Look up the speed of light in vacuum and calculate how far light travels in 1.5 seconds.",
    },
    {
        "order": 20,
        "title": "Three-tool research task",
        "description": "Create a query that requires three different tools, such as weather, conversion, and analysis or search.",
        "difficulty": Challenge.ADVANCED,
        "expected_tools": ["weather", "unit_converter", "web_search"],
        "points": 200,
        "sample_query": "Get the weather in Hyderabad, convert the temperature to Fahrenheit, and search for one recent news headline about Hyderabad.",
    },
]


class Command(BaseCommand):
    help = "Load the predefined AgentLab learning challenges."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for item in CHALLENGES:
            obj, was_created = Challenge.objects.update_or_create(
                order=item["order"],
                defaults={
                    "title": item["title"],
                    "description": item["description"],
                    "difficulty": item["difficulty"],
                    "expected_tools": item["expected_tools"],
                    "points": item["points"],
                    "sample_query": item["sample_query"],
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(f"Seeded challenges ({created} created, {updated} updated)."))
