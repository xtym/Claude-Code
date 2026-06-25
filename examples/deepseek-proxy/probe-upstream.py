import json
import time
import httpx

BASE = "https://model.wangbinjie.top/v1"
KEY = "freebuff"
MODEL = "deepseek/deepseek-v4-flash"

cases = [
    ("minimal", {"model": MODEL, "messages": [{"role": "user", "content": "ok"}], "max_tokens": 8}),
    ("no_max_tokens", {"model": MODEL, "messages": [{"role": "user", "content": "ok"}]}),
    ("stream", {"model": MODEL, "messages": [{"role": "user", "content": "ok"}], "max_tokens": 8, "stream": True}),
]

headers_variants = [
    {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json", "User-Agent": "curl/8.0"},
    {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
]

for name, body in cases:
    for i, hdrs in enumerate(headers_variants):
        url = f"{BASE}/chat/completions"
        t0 = time.time()
        try:
            with httpx.Client(timeout=120.0) as c:
                r = c.post(url, headers=hdrs, json=body)
            dt = time.time() - t0
            snippet = r.text[:120].replace("\n", " ")
            print(f"{name} hdr{i}: {r.status_code} {dt:.1f}s {snippet}")
        except Exception as e:
            print(f"{name} hdr{i}: ERR {type(e).__name__} {e}")
