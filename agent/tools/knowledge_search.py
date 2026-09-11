"""Public Wikipedia / knowledge lookup. No API key required."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

from agent.services.http_client import HttpError, get_json

NAME = "knowledge_search"
CATEGORY = "Public API"
DESCRIPTION = "Looks up encyclopedic facts from Wikipedia's public API."
REQUIRES_API_KEY = None
EXAMPLES = [
    "Who invented Python?",
    "What is Django?",
    "Give a short overview of function calling.",
]

SCHEMA = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "Look up stable encyclopedic or factual background knowledge from Wikipedia. "
            "Use this for definitions, people, places, and established concepts. "
            "Use web_search instead for breaking news or rapidly changing current events."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The topic or question to look up."},
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
            "error": "Please provide a knowledge query.",
            "summary": "Missing query.",
            "data": {},
        }

    try:
        search = get_json(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": 3,
                "utf8": 1,
            },
        )
    except HttpError as exc:
        return {"success": False, "error": str(exc), "summary": str(exc), "data": {}}

    hits = ((search.get("query") or {}).get("search") or [])
    if not hits:
        return {
            "success": True,
            "error": None,
            "summary": f"No Wikipedia results for '{query}'.",
            "data": {"query": query, "results": []},
        }

    title = hits[0].get("title") or query
    try:
        summary_payload = get_json(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}"
        )
    except HttpError:
        summary_payload = {}

    extract = summary_payload.get("extract") or hits[0].get("snippet") or ""
    url = (summary_payload.get("content_urls") or {}).get("desktop", {}).get("page") or (
        f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
    )
    related = [
        {
            "title": item.get("title"),
            "snippet": item.get("snippet", ""),
        }
        for item in hits
    ]
    data = {
        "query": query,
        "title": title,
        "url": url,
        "extract": extract,
        "related": related,
        "source": "Wikipedia",
    }
    short = extract[:180] + ("..." if len(extract) > 180 else "")
    return {
        "success": True,
        "error": None,
        "summary": f"{title}: {short}",
        "data": data,
    }
