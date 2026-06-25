import time
import httpx

BASE = "https://model.wangbinjie.top/v1"
KEY = "freebuff"
MODEL = "deepseek/deepseek-v4-flash"
UAS = [
    "curl/8.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "python-httpx/0.28",
    None,
]

body = {"model": MODEL, "messages": [{"role": "user", "content": "say ok"}], "max_tokens": 16}

def try_once(ua):
    hdrs = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    if ua:
        hdrs["User-Agent"] = ua
    with httpx.Client(timeout=120.0) as c:
        r = c.post(f"{BASE}/chat/completions", headers=hdrs, json=body)
    return r.status_code, r.text[:80]

ok = 0
for i in range(12):
    ua = UAS[i % len(UAS)]
    try:
        code, snip = try_once(ua)
        label = ua or "(none)"
        print(f"#{i+1} UA={label!r}: {code} {snip}")
        if code == 200:
            ok += 1
    except Exception as e:
        print(f"#{i+1} UA={ua!r}: ERR {e}")
    time.sleep(1)

print(f"success rate: {ok}/12")
