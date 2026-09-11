"""Small HTTP helper with timeouts. Uses the Python standard library only."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from django.conf import settings

USER_AGENT = "AgentLab/1.0 (educational Django AI agent; contact: local-dev)"


class HttpError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def get_json(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int | None = None,
) -> Any:
    if params:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{query}"

    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        request_headers.update(headers)

    timeout = timeout if timeout is not None else getattr(settings, "AGENT_API_TIMEOUT", 12)
    request = urllib.request.Request(url, headers=request_headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            if not raw:
                return {}
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            body = ""
        status = getattr(exc, "code", None)
        if status == 401:
            raise HttpError("The API rejected the request (invalid API key).", status) from exc
        if status == 404:
            raise HttpError("The requested resource was not found.", status) from exc
        if status == 429:
            raise HttpError("The API rate limit was reached. Please try again later.", status) from exc
        raise HttpError(f"The remote API returned HTTP {status}. {body}".strip(), status) from exc
    except urllib.error.URLError as exc:
        raise HttpError("The remote API could not be reached (network or timeout).") from exc
    except TimeoutError as exc:
        raise HttpError("The remote API timed out.") from exc
    except json.JSONDecodeError as exc:
        raise HttpError("The remote API returned invalid JSON.") from exc
