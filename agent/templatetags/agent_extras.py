from __future__ import annotations

import html
import json
import re

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_BOLD_UNDERSCORE = re.compile(r"__(.+?)__")
_ITALIC = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_INLINE_CODE = re.compile(r"`([^`]+)`")
_FENCE = re.compile(r"```[\w+-]*\n?(.*?)```", re.S)


def _inline(text: str) -> str:
    text = _INLINE_CODE.sub(r"<code>\1</code>", text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _BOLD_UNDERSCORE.sub(r"<strong>\1</strong>", text)
    text = _ITALIC.sub(r"<em>\1</em>", text)
    return text


def format_agent_html(text: str) -> str:
    if not text or not str(text).strip():
        return ""

    source = html.escape(str(text).replace("\r\n", "\n").strip())
    fences: list[str] = []

    def _store_fence(match: re.Match) -> str:
        fences.append(f"<pre><code>{match.group(1).strip()}</code></pre>")
        return f"@@FENCE{len(fences) - 1}@@"

    source = _FENCE.sub(_store_fence, source)
    blocks = re.split(r"\n{2,}", source)
    rendered: list[str] = []

    for block in blocks:
        token = block.strip()
        if not token:
            continue
        fence_match = re.fullmatch(r"@@FENCE(\d+)@@", token)
        if fence_match:
            rendered.append(fences[int(fence_match.group(1))])
            continue

        lines = [line.rstrip() for line in token.split("\n") if line.strip()]
        header_match = re.match(r"^(#{1,6})\s+(.*)$", token.strip())
        if header_match:
            level = len(header_match.group(1))
            title_text = _inline(header_match.group(2))
            h_tag = f"h{min(level + 1, 6)}"
            rendered.append(f"<{h_tag}>{title_text}</{h_tag}>")
            continue

        bullet_items = []
        numbered_items = []
        for line in lines:
            bullet = re.match(r"^[-•]\s+(.*)$", line)
            numbered = re.match(r"^\d+[.)]\s+(.*)$", line)
            if bullet:
                bullet_items.append(bullet.group(1))
            if numbered:
                numbered_items.append(numbered.group(1))
        if lines and len(bullet_items) == len(lines):
            items = "".join(f"<li>{_inline(item)}</li>" for item in bullet_items)
            rendered.append(f"<ul>{items}</ul>")
            continue
        if lines and len(numbered_items) == len(lines):
            items = "".join(f"<li>{_inline(item)}</li>" for item in numbered_items)
            rendered.append(f"<ol>{items}</ol>")
            continue
        paragraph = _inline("<br>".join(lines))
        rendered.append(f"<p>{paragraph}</p>")

    return "".join(rendered)


@register.filter(name="render_answer")
def render_answer(value) -> str:
    return mark_safe(format_agent_html(value or ""))


@register.filter(name="plain_preview")
def plain_preview(value, length: int = 280) -> str:
    text = re.sub(r"[*_`#]+", "", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    limit = int(length)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


@register.filter(name="pretty_data")
def pretty_data(value) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, ensure_ascii=False)
    return str(value or "")
