import os, httpx
from playwright.sync_api import sync_playwright
A = os.getenv("TWKS_ADSPOWER_URL", "http://127.0.0.1:50325").rstrip("/")
K = os.getenv("TWKS_ADSPOWER_KEY", "")
AK = {"Authorization": "Bearer " + K} if K else {}
d = httpx.get(A + "/api/v1/browser/local-active", headers=AK, timeout=30).json()
items = (d.get("data") or {}).get("list") or []
print("активных:", len(items))
pid = items[0]["user_id"]
s = httpx.get(A + "/api/v1/browser/start", params={"user_id": pid}, headers=AK, timeout=60).json()
ws = ((s.get("data") or {}).get("ws") or {}).get("puppeteer", "")
with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp(ws)
    ctx = b.contexts[0]
    pages = [p for p in ctx.pages if not p.is_closed()]
    page = pages[-1]
    print("url:", page.url)
    page.wait_for_timeout(1000)
    fields = page.evaluate("() => [...document.querySelectorAll('input,textarea,[contenteditable]')].map(e => e.outerHTML.slice(0,200))")
    print("ПОЛЕЙ:", len(fields))
    for f in fields:
        print(f)
    print("iframe:", page.evaluate("() => document.querySelectorAll('iframe').length"))
