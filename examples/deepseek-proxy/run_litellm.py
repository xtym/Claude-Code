"""Start LiteLLM proxy with httpx retry + User-Agent rotation for flaky gateways.

Patches outbound HTTP before LiteLLM loads so freebuff / model.wangbinjie.top
can work without changing OPENAI_API_BASE.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
FALLBACK_UAS = [
    DEFAULT_UA,
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "curl/8.0",
]
BLOCKED_REQUEST_UA_PREFIXES = ("openai/", "python-httpx", "litellm/")


def _user_agents() -> list[str]:
    primary = os.environ.get("UPSTREAM_USER_AGENT", DEFAULT_UA).strip()
    seen: set[str] = set()
    out: list[str] = []
    for ua in [primary, *FALLBACK_UAS]:
        if ua and ua not in seen:
            seen.add(ua)
            out.append(ua)
    return out


def _should_retry_status(code: int) -> bool:
    return code in (403, 502, 503, 520, 521, 522, 524)


def _patch_sync_client() -> None:
    _orig = httpx.Client.request

    def _request(self, method, url, **kwargs):
        headers = dict(kwargs.get("headers") or {})
        last_exc: Exception | None = None
        max_attempts = int(os.environ.get("UPSTREAM_MAX_RETRIES", "4"))
        uas = _user_agents()
        for attempt in range(max_attempts):
            ua = uas[attempt % len(uas)]
            req_headers = dict(headers)
            existing = str(req_headers.get("User-Agent", "")).lower()
            if not existing or any(existing.startswith(p) for p in BLOCKED_REQUEST_UA_PREFIXES):
                req_headers["User-Agent"] = ua
            kwargs["headers"] = req_headers
            try:
                resp = _orig(self, method, url, **kwargs)
                if _should_retry_status(resp.status_code) and attempt < max_attempts - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                return resp
            except (httpx.HTTPError, OSError) as exc:
                last_exc = exc
                if attempt < max_attempts - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise
        if last_exc:
            raise last_exc
        return _orig(self, method, url, **kwargs)

    httpx.Client.request = _request  # type: ignore[method-assign]


def _patch_async_client() -> None:
    _orig = httpx.AsyncClient.request

    async def _request(self, method, url, **kwargs):
        import asyncio

        headers = dict(kwargs.get("headers") or {})
        last_exc: Exception | None = None
        max_attempts = int(os.environ.get("UPSTREAM_MAX_RETRIES", "4"))
        uas = _user_agents()
        for attempt in range(max_attempts):
            ua = uas[attempt % len(uas)]
            req_headers = dict(headers)
            existing = str(req_headers.get("User-Agent", "")).lower()
            if not existing or any(existing.startswith(p) for p in BLOCKED_REQUEST_UA_PREFIXES):
                req_headers["User-Agent"] = ua
            kwargs["headers"] = req_headers
            try:
                resp = await _orig(self, method, url, **kwargs)
                if _should_retry_status(resp.status_code) and attempt < max_attempts - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                return resp
            except (httpx.HTTPError, OSError) as exc:
                last_exc = exc
                if attempt < max_attempts - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                raise
        if last_exc:
            raise last_exc
        return await _orig(self, method, url, **kwargs)

    httpx.AsyncClient.request = _request  # type: ignore[method-assign]


def main() -> None:
    _patch_sync_client()
    _patch_async_client()

    from litellm.proxy.proxy_cli import run_server

    config = HERE / "litellm_config.generated.yaml"
    if not config.exists():
        print(f"Missing {config} — run start-litellm.ps1 first to generate it.", file=sys.stderr)
        sys.exit(1)

    host = os.environ.get("PROXY_HOST", "127.0.0.1")
    port = os.environ.get("PROXY_PORT", "4000")
    sys.argv = [
        "run_litellm",
        "--config",
        str(config),
        "--host",
        host,
        "--port",
        port,
    ]
    run_server()


if __name__ == "__main__":
    main()
