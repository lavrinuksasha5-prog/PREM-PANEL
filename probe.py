import json, os, time
import httpx
from playwright.sync_api import sync_playwright

A = os.getenv("TWKS_ADSPOWER_URL", "http://127.0.0.1:50325").rstrip("/")
K = os.getenv("TWKS_ADSPOWER_KEY", "")
AK = {"Authorization": "Bearer " + K} if K else {}
P = "socks5://luJyhieLc5:qoeS2WvKEf@proxy.proxyma.io:10000"

s, rest = P.split("://", 1)
auth, _, hostport = rest.rpartition("@")
user, _, pwd = auth.partition(":")
host, _, port = hostport.partition(":")

body = {
    "name": "probe_" + str(int(time.time())),
    "group_id": "0",
    "domain_name": "web.telegram.org",
    "user_proxy_config": {
        "proxy_soft": "other", "proxy_type": s,
        "proxy_host": host, "proxy_port": port,
        "proxy_user": user, "proxy_password": pwd,
    },
}
d = httpx.post(A + "/api/v1/user/create", json=body, headers=AK, timeout=60).json()
print("create:", str(d)[:160])
pid = d["data"]["id"]
st = httpx.get(A + "/api/v1/browser/start", params={"user_id": pid, "ip_tab": "0"}, headers=AK, timeout=60).json()
ws = ((st.get("data") or {}).get("ws") or {}).get("puppeteer", "")

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp(ws)
    time.sleep(3)
    ctx = b.contexts[0]
    pages = [p for p in ctx.pages if not p.is_closed()]
    page = pages[-1] if pages else ctx.new_page()
    page.goto("https://web.telegram.org/k/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(6000)
    try:
        page.locator("text=/LOG IN BY PHONE NUMBER/i").first.click(timeout=15000)
        print("клик по номеру: ok")
    except Exception as e:
        print("клик не вышел:", e.__class__.__name__)
    page.wait_for_timeout(4000)
    print("url:", page.url)
    items = page.evaluate("() => [...document.querySelectorAll('input,textarea,[contenteditable]')].map(e => e.outerHTML.slice(0,220))")
    print("ПОЛЕЙ:", len(items))
    for item in items:
        print(item)
    page.screenshot(path="C:/twks/shots/probe.png")
