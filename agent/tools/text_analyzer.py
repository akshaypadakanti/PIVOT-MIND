"""Lightweight text statistics for educational analysis."""
from __future__ import annotations

import re
from typing import Any

NAME = "analyze_text"
CATEGORY = "Local"
DESCRIPTION = "Counts characters, words, sentences, paragraphs, and average words per sentence."
REQUIRES_API_KEY = None
EXAMPLES = [
    "Analyze this paragraph: Django is a Python web framework.",
    "How many words are in this sentence?",
    "Analyze the text I provide for sentence length.",
]

SCHEMA = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": "Analyze supplied text and return character, word, sentence, and paragraph counts.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The text to analyze."},
            },
            "required": ["text"],
        },
    },
}


def analyze(text: str) -> dict[str, Any]:
    raw = text or ""
    characters = len(raw)
    characters_no_spaces = len(re.sub(r"\s+", "", raw))
    words = re.findall(r"\b[\w']+\b", raw)
    paragraphs = [block for block in re.split(r"\n\s*\n", raw.strip()) if block.strip()] if raw.strip() else []
    sentences = [part.strip() for part in re.split(r"[.!?]+\s*", raw.strip()) if part.strip()]
    sentence_count = len(sentences)
    word_count = len(words)
    average = round(word_count / sentence_count, 2) if sentence_count else 0
    return {
        "characters": characters,
        "characters_without_spaces": characters_no_spaces,
        "words": word_count,
        "sentences": sentence_count,
        "paragraphs": len(paragraphs),
        "average_words_per_sentence": average,
    }


def execute(text: str) -> dict[str, Any]:
    if text is None or not str(text).strip():
        return {
            "success": False,
            "error": "Please provide text to analyze.",
            "summary": "Missing text.",
            "data": {},
        }
    data = analyze(str(text))
    summary = (
        f"{data['characters']} chars, {data['words']} words, "
        f"{data['sentences']} sentences, {data['paragraphs']} paragraphs"
    )
    return {"success": True, "error": None, "summary": summary, "data": data}
