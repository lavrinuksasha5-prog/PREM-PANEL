import json, os, time
import httpx

P = os.getenv("TWKS_PANEL_URL", "http://127.0.0.1:8000").rstrip("/")
T = os.getenv("TWKS_AGENT_TOKEN", "agent-secret")
A = os.getenv("TWKS_ADSPOWER_URL", "http://127.0.0.1:50325").rstrip("/")
K = os.getenv("TWKS_ADSPOWER_KEY", "")
H = {"X-Agent-Token": T, "Content-Type": "application/json"}
AK = {"Authorization": "Bearer " + K} if K and K.isascii() else {}
S = {}


def g(path, q):
    r = httpx.get(A + path, params=q, headers=AK, timeout=60)
    r.raise_for_status()
    return r.json()


def pj(path, body):
    r = httpx.post(A + path, json=body, headers=AK, timeout=60)
    r.raise_for_status()
    return r.json()


def sp(u):
    s, x = "http", u
    if "://" in u:
        s, x = u.split("://", 1)
    a, _, hp = x.rpartition("@")
    us, _, pw = a.partition(":")
    h, _, pt = hp.partition(":")
    return s, h, pt, us, pw


def nav(ws):
    if not ws:
        return
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright нет", flush=True)
        return
    try:
        with sync_playwright() as pw:
            b = pw.chromium.connect_over_cdp(ws)
            ctx = b.contexts[0] if b.contexts else b.new_context()
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto("https://web.telegram.org/a/", wait_until="domcontentloaded", timeout=60000)
            print("сайт открыт", flush=True)
    except Exception as e:
        print("nav err", e, flush=True)


def alive():
    try:
        d = g("/api/v1/browser/local-active", {})
        items = (d.get("data") or {}).get("list") or []
        ids = [str(i.get("user_id")) for i in items if i.get("user_id")]
        if ids:
            return ids
    except Exception:
        pass
    return list(S.keys())


def run(c):
    k = c["kind"]
    p = c.get("payload", {})
    a = p.get("account_id")
    try:
        if k == "open_profile":
            s, h, pt, us, pw = sp(p.get("proxy", ""))
            body = {
                "name": p.get("profile_name", "twks"),
                "group_id": "0",
                "domain_name": "web.telegram.org",
            }
            if h and pt:
                body["user_proxy_config"] = {
                    "proxy_soft": "other",
                    "proxy_type": "socks5" if s == "socks5" else "http",
                    "proxy_host": h,
                    "proxy_port": pt,
                    "proxy_user": us,
                    "proxy_password": pw,
                }
            d = pj("/api/v1/user/create", body)
            if d.get("code") not in (0, "0"):
                raise Exception(d.get("msg"))
            pid = d["data"]["id"]
            d2 = g("/api/v1/browser/start", {"user_id": pid, "ip_tab": "0"})
            ws = ((d2.get("data") or {}).get("ws") or {}).get("puppeteer", "")
            S[pid] = ws
            print("opened", pid, flush=True)
            nav(ws)
            try:
                from tg_login import login as tg_login
                print('login:', tg_login(ws, a), flush=True)
            except Exception as e:
                print('login err', e.__class__.__name__, flush=True)
            return {"ok": True, "account_id": a, "profile_id": pid, "session": None}
        if k == "close_profile":
            pid = str(p.get("profile_id", ""))
            if pid:
                try:
                    g("/api/v1/browser/stop", {"user_id": pid})
                except Exception:
                    pass
                try:
                    pj("/api/v1/user/delete", {"user_ids": [pid]})
                except Exception:
                    pass
                S.pop(pid, None)
            return {"ok": True, "account_id": a, "profile_id": pid, "session": None}
        return {"ok": False, "error": "unknown"}
    except Exception as e:
        print("ERR", e, flush=True)
        return {"ok": False, "account_id": a, "error": str(e)[:300]}


def cleanup():
    try:
        d = g("/api/v1/browser/local-active", {})
        active = set(str(i.get("user_id")) for i in ((d.get("data") or {}).get("list") or []))
        lst = g("/api/v1/user/list", {"page": 1, "page_size": 100})
        rows = ((lst.get("data") or {}).get("list") or [])
        pass
        ids = [str(r.get("user_id") or r.get("id")) for r in rows if str(r.get("user_id") or r.get("id")) not in active]
        if ids:
            [print("del:", one, str(httpx.post(A + "/api/v1/user/delete", json={"user_ids": [one]}, headers=AK, timeout=60).text)[:90], flush=True) for one in ids]
            pass
            print("cleanup", len(ids), flush=True)
    except Exception as e:
        print("cleanup skip", e.__class__.__name__, flush=True)

def _run_and_send(c):
    res = run(c)
    try:
        httpx.post(P + "/api/agent/result", json={"command_id": c["id"], "status": "done" if res.get("ok") else "error", "result": res}, headers=H, timeout=20)
    except Exception as e:
        print("result err", e.__class__.__name__, flush=True)

print("ads bridge ->", P, flush=True)
while True:
    try:
        cleanup()
        r = httpx.post(P + "/api/agent/poll", json={"agent_id": "default", "alive": alive()}, headers=H, timeout=20)
        if r.status_code == 401:
            print("bad token", flush=True)
            time.sleep(10)
            continue
        for c in r.json().get("commands", []):
            print("cmd", c["kind"], flush=True)
            if c["kind"] == "open_profile":
                import threading
                threading.Thread(target=_run_and_send, args=(c,), daemon=True).start()
            else:
                _run_and_send(c)
    except Exception as e:
        print("panel err", e, flush=True)
    time.sleep(2)










