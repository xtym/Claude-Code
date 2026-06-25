"""LiteLLM hook: force browser-like User-Agent for flaky gateways (e.g. freebuff).

Gateways such as model.wangbinjie.top block:
  - OpenAI/Python (403)
  - curl/8.0 (502 Cloudflare)
and accept:
  - Mozilla/5.0 ...

Set UPSTREAM_USER_AGENT in .env (see .env.example).
"""

from __future__ import annotations

import os

from litellm.integrations.custom_logger import CustomLogger

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

BLOCKED_UA_PREFIXES = ("openai/", "curl/", "python-httpx", "litellm")


def _target_user_agent() -> str:
    return os.environ.get("UPSTREAM_USER_AGENT", DEFAULT_UA).strip() or DEFAULT_UA


class UpstreamResilienceHandler(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        ua = _target_user_agent()
        extra = dict(data.get("extra_headers") or {})
        existing = str(extra.get("User-Agent", "")).lower()
        if not existing or any(existing.startswith(p) for p in BLOCKED_UA_PREFIXES):
            extra["User-Agent"] = ua
        data["extra_headers"] = extra
        return data
