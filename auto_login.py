import asyncio, os, random, sys, threading, time
from pathlib import Path
import httpx
from tg_helper import phone_of, wait_code

A = os.getenv("TWKS_ADSPOWER_URL", "http://127.0.0.1:50325").rstrip("/")
K = os.getenv("TWKS_ADSPOWER_KEY", "")
AK = {"Authorization": "Bearer " + K} if K and K.isascii() else {}
SH = Path(__file__).resolve().parent / "shots"
SH.mkdir(exist_ok=True)

COUNTRY = {
    "30": "Greece", "7": "Russia", "380": "Ukraine", "375": "Belarus", "48": "Poland",
    "49": "Germany", "1": "United States", "44": "United Kingdom", "90": "Turkey",
    "995": "Georgia", "971": "United Arab Emirates", "996": "Kyrgyzstan",
    "998": "Uzbekistan", "994": "Azerbaijan", "992": "Tajikistan", "966": "Saudi Arabia",
    "972": "Israel", "370": "Lithuania", "371": "Latvia", "372": "Estonia",
    "420": "Czechia", "36": "Hungary", "40": "Romania", "39": "Italy", "34": "Spain",
    "33": "France", "31": "Netherlands", "32": "Belgium", "43": "Austria", "41": "Switzerland",
}
PRE = sorted(COUNTRY.keys(), key=len, reverse=True)


def split_phone(ph):
    for p in PRE:
        if ph.startswith(p):
            return p, ph[len(p):]
    return ph[:2], ph[2:]


def sp(u):
    s, x = "http", u
    if "://" in u:
        s, x = u.split("://", 1)
    a, _, hp = x.rpartition("@")
    us, _, pw = a.partition(":")
    h, _, pt = hp.partition(":")
    return s, h, pt, us, pw


def open_profile(name, proxy):
    s, h, pt, us, pw = sp(proxy)
    body = {"name": name, "group_id": "0", "domain_name": "web.telegram.org",
            "user_proxy_config": {"proxy_soft": "other",
                                  "proxy_type": "socks5" if s == "socks5" else "http",
                                  "proxy_host": h, "proxy_port": pt,
                                  "proxy_user": us, "proxy_password": pw}}
    d = httpx.post(A + "/api/v1/user/create", json=body, headers=AK, timeout=60).json()
    if d.get("code") not in (0, "0"):
        raise RuntimeError(str(d.get("msg")))
    pid = d["data"]["id"]
    print("профиль:", pid, flush=True)
    st = httpx.get(A + "/api/v1/browser/start", params={"user_id": pid, "ip_tab": "0"}, headers=AK, timeout=60).json()
    ws = ((st.get("data") or {}).get("ws") or {}).get("puppeteer", "")
    print("окно запущено", flush=True)
    return pid, ws


def fresh(browser):
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    for _ in range(20):
        pages = [p for p in ctx.pages if not p.is_closed()]
        if pages:
            return ctx, pages[-1]
        time.sleep(0.3)
    return ctx, ctx.new_page()


def click(page, pattern, t=8000):
    for _ in range(2):
        try:
            page.locator(pattern).first.click(timeout=t)
            return True
        except Exception:
            time.sleep(1)
    return False


def set_country(page, name):
    try:
        page.locator("#sign-in-phone-code").first.click(timeout=8000)
        page.keyboard.press("Control+A")
        page.keyboard.press("Delete")
        for ch in name:
            page.keyboard.type(ch)
            time.sleep(random.uniform(0.04, 0.09))
        page.wait_for_timeout(900)
        clicked = click(page, "text=" + name, t=6000)
        page.wait_for_timeout(700)
        print("страна выбрана:", clicked, flush=True)
        return clicked
    except Exception as exc:
        print("страна не выбралась:", exc.__class__.__name__, flush=True)
        return False


def type_digits(page, selector, value, lo=0.09, hi=0.16):
    try:
        page.locator(selector).first.wait_for(state="visible", timeout=8000)
        page.eval_on_selector(selector, "el => { el.focus(); el.select && el.select(); }")
        page.keyboard.press("Control+A")
        page.keyboard.press("Delete")
        for ch in str(value):
            page.keyboard.type(ch)
            time.sleep(random.uniform(lo, hi))
        return True
    except Exception as exc:
        print("ввод не вышел:", selector, exc.__class__.__name__, flush=True)
        return False

def main():
    acc = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    proxy = sys.argv[2] if len(sys.argv) > 2 else ""
    from playwright.sync_api import sync_playwright

    print("читаю телефон...", flush=True)
    ph = asyncio.run(phone_of(acc))
    print("телефон: +" + ph, flush=True)
    if not ph:
        raise SystemExit("нет номера")
    cc, nat = split_phone(ph)
    country = COUNTRY.get(cc, "")
    print("код:", cc, "номер:", nat, "страна:", country, flush=True)

    pid, ws = open_profile("auto_" + str(acc), proxy)
    box = {}

    def grab():
        try:
            box["code"] = asyncio.run(wait_code(acc, 180))
        except Exception as e:
            box["err"] = str(e)

    with sync_playwright() as pw:
        br = pw.chromium.connect_over_cdp(ws)
        ctx, page = fresh(br)
        time.sleep(1)
        for _ in range(3):
            try:
                page.goto("https://web.telegram.org/a/", wait_until="domcontentloaded", timeout=60000)
                break
            except Exception:
                ctx, page = fresh(br)
                time.sleep(1)
        page.wait_for_timeout(3500)
        print("открыт:", page.url, flush=True)

        click(page, "text=/LOG IN BY PHONE NUMBER/i")
        page.wait_for_timeout(1500)
        print("форма:", page.url, flush=True)

        if country:
            set_country(page, country)

        ok = type_digits(page, "#sign-in-phone-number", cc + nat)
        print("номер введён:", ok, flush=True)
        page.screenshot(path=str(SH / "phone.png"))

        click(page, "text=/^next$/i")
        print("жду код...", flush=True)

        th = threading.Thread(target=grab, daemon=True)
        th.start()
        th.join(timeout=190)
        code = box.get("code", "")
        print("код:", code or "не получил", flush=True)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(SH / "code_screen.png"))

        if code:
            ok = type_digits(page, "#sign-in-code", code)
            print("код введён:", ok, flush=True)
            page.wait_for_timeout(600)
            click(page, "text=/^next$/i")
            page.wait_for_timeout(6000)
            page.screenshot(path=str(SH / "after_code.png"))
            print("URL:", page.url, flush=True)
            if page.locator("input[type=password]").count() > 0:
                print("!!! нужен пароль 2FA", flush=True)
            try:
                page.goto("https://web.telegram.org/k/", wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(3000)
                print("K версия:", page.url, flush=True)
            except Exception:
                pass

        page.screenshot(path=str(SH / "final.png"))
        print("профиль:", pid, flush=True)
        input("Enter — окно остаётся открытым...")


if __name__ == "__main__":
    main()

