"""Web search via SerpAPI. Never fakes results when unconfigured."""
from __future__ import annotations

from typing import Any

from django.conf import settings

from agent.services.http_client import HttpError, get_json

NAME = "web_search"
CATEGORY = "External API"
DESCRIPTION = "Searches the live web with SerpAPI and returns titles, URLs, snippets, and sources."
REQUIRES_API_KEY = "SERPAPI_API_KEY"
EXAMPLES = [
    "What is the latest Python version?",
    "Search for the latest AI news.",
    "Who is the current CEO of Microsoft?",
    "Find information about Django.",
]

SCHEMA = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "Search the public web for current information, news, people, versions, "
            "and facts that may change. Returns titles, URLs, and snippets."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to send to the web search engine.",
                }
            },
            "required": ["query"],
        },
    },
}


def execute(query: str) -> dict[str, Any]:
    query = (query or "").strip()
    if not query:
        return {
            "success": False,
            "error": "Please provide a search query.",
            "summary": "Missing search query.",
            "data": {},
        }

    api_key = getattr(settings, "SERPAPI_API_KEY", "") or ""
    if not api_key:
        message = "SerpAPI is not configured. Set SERPAPI_API_KEY to enable web search."
        return {"success": False, "error": message, "summary": message, "data": {"configured": False}}

    try:
        payload = get_json(
            "https://serpapi.com/search.json",
            params={"engine": "google", "q": query, "api_key": api_key, "num": 5},
        )
    except HttpError as exc:
        return {"success": False, "error": str(exc), "summary": str(exc), "data": {}}

    if payload.get("error"):
        message = str(payload["error"])
        return {"success": False, "error": message, "summary": message, "data": {}}

    results = []
    for item in payload.get("organic_results", [])[:5]:
        results.append(
            {
                "title": item.get("title") or "Untitled",
                "url": item.get("link") or "",
                "snippet": item.get("snippet") or "",
                "source": item.get("source") or item.get("displayed_link") or "",
            }
        )

    if not results:
        return {
            "success": True,
            "error": None,
            "summary": f"No web results found for '{query}'.",
            "data": {"query": query, "results": []},
        }

    top = results[0]
    return {
        "success": True,
        "error": None,
        "summary": f"{top['title']} — {top['snippet'][:140]}",
        "data": {"query": query, "results": results},
    }
