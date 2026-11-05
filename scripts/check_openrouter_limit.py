"""One minimal inference probe; print only allowlisted rate-limit metadata."""

import json
import os
import re

import httpx

from merchant_triage.openrouter import DEFAULT_MODEL


def safe_diagnostic(response):
    result = {"http_status": response.status_code, "model": DEFAULT_MODEL,
              "probe": "one minimal request; no merchant/store data"}
    if response.status_code != 429:
        result["limit_scope"] = "not_rate_limited" if response.is_success else "other_http_error"
        return result
    try:
        error = response.json().get("error", {})
        message = str(error.get("message", "")).lower()
        metadata_headers = error.get("metadata", {}).get("headers", {})
    except (ValueError, AttributeError, TypeError):
        message, metadata_headers = "", {}
    if "free-models-per-day" in message:
        result["limit_scope"] = "free_models_per_day"
    elif "free-models-per-min" in message:
        result["limit_scope"] = "free_models_per_minute"
    else:
        result["limit_scope"] = "unspecified_429"
    headers = dict(response.headers)
    if isinstance(metadata_headers, dict):
        headers.update({str(key).lower(): str(value) for key, value in metadata_headers.items()})
    result["rate_limit_headers"] = {
        name: value for name in ("x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset", "retry-after")
        if (value := headers.get(name)) is not None and re.fullmatch(r"[0-9.]+", value)
    }
    return result


if __name__ == "__main__":
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not configured")
    try:
        response = httpx.post("https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"}, timeout=45,
            json={"model": DEFAULT_MODEL, "messages": [{"role": "user", "content": "Reply OK."}],
                  "max_tokens": 16, "temperature": 0, "reasoning": {"enabled": False}})
        print(json.dumps(safe_diagnostic(response), indent=2))
    except httpx.TransportError:
        raise SystemExit("OpenRouter diagnostic network request failed") from None
