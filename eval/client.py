"""OpenAI-compatible chat client. stdlib urllib, retries, never raises."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

RETRY_CODES = (408, 409, 425, 429, 500, 502, 503, 504, 522, 524)


def _post(url: str, payload: dict, api_key: str, timeout: int) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def chat(
    messages: list[dict],
    model: str,
    api_key: str,
    base_url: str,
    max_tokens: int = 1600,
    temperature: float = 0.7,
    retries: int = 5,
    timeout: int = 180,
) -> dict[str, Any]:
    """One completion. Failures come back as ok=False with an error string, never as a raise."""
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    error = ""
    for attempt in range(retries):
        started = time.time()
        try:
            body = _post(url, payload, api_key, timeout)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            error = "HTTP %s: %s" % (exc.code, detail)
            if exc.code in RETRY_CODES:
                time.sleep(1.5 * (attempt + 1))
                continue
            break
        except Exception as exc:  # noqa: BLE001 - reported as data, not raised
            error = "%s: %s" % (type(exc).__name__, exc)
            time.sleep(1.5 * (attempt + 1))
            continue

        latency_ms = int((time.time() - started) * 1000)
        choice = (body.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        text = (message.get("content") or "").strip()
        reasoning = (message.get("reasoning_content") or "").strip()
        usage = body.get("usage") or {}

        # A reasoning model spends max_tokens on reasoning first, so empty content with a
        # length finish is a truncation rather than an answer. Give it room and retry instead
        # of recording a blank as if it were a result.
        if not text and reasoning and attempt + 1 < retries:
            payload["max_tokens"] = min(payload["max_tokens"] * 2, 8000)
            error = "empty content, reasoning only (finish=%s); retried at %s tokens" % (
                choice.get("finish_reason"),
                payload["max_tokens"],
            )
            continue

        return {
            "ok": bool(text),
            "error": "" if text else "empty content (finish=%s)" % choice.get("finish_reason"),
            "text": text,
            "reasoning_chars": len(reasoning),
            "finish": choice.get("finish_reason"),
            "usage": {
                "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                "completion_tokens": int(usage.get("completion_tokens") or 0),
                "total_tokens": int(usage.get("total_tokens") or 0),
            },
            "latency_ms": latency_ms,
            "model": body.get("model", model),
            "attempts": attempt + 1,
        }
    return {
        "ok": False,
        "error": error or "unknown error",
        "text": "",
        "reasoning_chars": 0,
        "finish": None,
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "latency_ms": 0,
        "model": model,
        "attempts": retries,
    }

