import asyncio, random, re, shutil, threading, time

PRE = "380 375 995 996 998 994 992 971 972 966 90 7 1 20 27 30 31 33 34 36 39 40 41 43 44 45 46 47 48 49 51 52 53 54 55 56 57 58 60 61 62 63 64 65 66 81 82 84 86 91 92 93 94 95 98".split()
PRE = sorted(PRE, key=len, reverse=True)


def split_phone(ph):
    for p in PRE:
        if ph.startswith(p):
            return p, ph[len(p):]
    return ph[:2], ph[2:]


def wait_any(page, selectors, timeout=25000):
    end = time.time() + timeout / 1000.0
    while time.time() < end:
        for s in selectors:
            try:
                if page.locator(s).count() > 0:
                    return s
            except Exception:
                pass
        time.sleep(0.4)
    return ""


def focused_id(page):
    try:
        return page.evaluate("() => (document.activeElement && document.activeElement.id) || ''")
    except Exception:
        return ""


def type_verified(page, selector, value, lo=0.08, hi=0.15):
    want = str(value)
    bare = want.replace("+", "").replace(" ", "")
    for attempt in range(3):
        try:
            page.locator(selector).first.wait_for(state="visible", timeout=20000)
        except Exception:
            print("вход: поле не появилось", selector, flush=True)
            return False
        page.eval_on_selector(selector, "el => { el.focus(); if (el.select) el.select(); }")
        page.wait_for_timeout(500)
        aid = focused_id(page)
        if selector.startswith("#") and aid != selector[1:]:
            print("вход: фокус не там, а в", aid or "?", flush=True)
            page.wait_for_timeout(800)
            continue
        page.keyboard.press("Control+A")
        page.keyboard.press("Delete")
        for ch in want:
            page.keyboard.type(ch)
            time.sleep(random.uniform(lo, hi))
        page.wait_for_timeout(700)
        try:
            got = page.input_value(selector).replace(" ", "").replace("+", "")
        except Exception:
            got = ""
        if bare in got:
            return True
        print("вход: цифры не легли, в поле:", got[:20], flush=True)
        page.wait_for_timeout(900)
    return False


def find_password(account_id, phone=""):
    import json as _json
    from tg_helper import WORK
    folder = WORK / str(account_id)
    files = [f for f in folder.rglob("*") if f.is_file()] if folder.exists() else []
    prefixes = []
    for f in files:
        if f.suffix.lower() != ".json":
            continue
        try:
            data = _json.loads(f.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        if phone and str(data.get("phone", "")) == phone:
            if "_" in f.name:
                prefixes.append(f.name.split("_")[0] + "_")
            for key in ("twoFA", "two_fa_password", "password"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    for f in files:
        if f.suffix.lower() != ".txt":
            continue
        if prefixes and not any(f.name.startswith(p) for p in prefixes):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            continue
        if text and " " not in text and 4 <= len(text) <= 64:
            print("вход: пароль из", f.name, flush=True)
            return text
        for line in text.splitlines():
            s = line.strip()
            if s and " " not in s and 4 <= len(s) <= 64:
                print("вход: пароль из", f.name, flush=True)
                return s
    for f in files:
        if f.suffix.lower() != ".txt":
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            continue
        for line in text.splitlines():
            s = line.strip()
            if s and " " not in s and 4 <= len(s) <= 64:
                return s
    return ""

def login(ws, account_id):
    from playwright.sync_api import sync_playwright
    from tg_helper import WORK, phone_of, wait_code

    folder = WORK / str(account_id)
    try:
        if folder.exists() and not any(folder.rglob("*.txt")):
            shutil.rmtree(folder, ignore_errors=True)
    except Exception:
        pass

    try:
        phone = asyncio.run(phone_of(account_id))
    except Exception as exc:
        print("вход: tdata fail", exc.__class__.__name__, flush=True)
        return False
    if not phone:
        print("вход: нет номера", flush=True)
        return False

    print("вход: +%s" % phone, flush=True)
    ok = False

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(ws)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        try:
            page.bring_to_front()
        except Exception:
            pass

        for attempt in range(1, 4):
            print("вход: попытка", attempt, flush=True)
            box = {}

            def grab():
                try:
                    box["code"] = asyncio.run(wait_code(account_id, 200))
                except Exception:
                    pass

            thread = threading.Thread(target=grab, daemon=True)
            thread.start()

            try:
                page.goto("https://web.telegram.org/a/", wait_until="domcontentloaded", timeout=60000)
            except Exception as exc:
                print("вход: goto fail", exc.__class__.__name__, flush=True)
            page.wait_for_timeout(3000)

            if not wait_any(page, ["#sign-in-phone-number"], 6000):
                try:
                    page.locator("text=/LOG IN BY PHONE NUMBER/i").first.click(timeout=10000)
                except Exception:
                    pass
                page.wait_for_timeout(2000)

            if not wait_any(page, ["#sign-in-phone-number"], 20000):
                print("вход: форма не появилась -> перезагрузка", flush=True)
                continue

            page.eval_on_selector("#sign-in-phone-number", "el => { el.focus(); }")
            page.wait_for_timeout(600)
            if not type_verified(page, "#sign-in-phone-number", "+" + phone):
                print("вход: номер не принят -> перезагрузка", flush=True)
                continue
            print("вход: номер набран", flush=True)

            page.wait_for_timeout(700)
            try:
                page.keyboard.press("Enter")
            except Exception:
                page.keyboard.press("Enter")

            print("вход: жду поле кода...", flush=True)
            if not wait_any(page, ["#sign-in-code"], 45000):
                print("вход: поле кода не появилось -> перезагрузка", flush=True)
                continue

            thread.join(timeout=200)
            code = box.get("code", "")
            print("вход: код", code or "не получил", flush=True)
            if not code:
                print("вход: кода нет -> перезагрузка", flush=True)
                continue

            page.wait_for_timeout(500)
            if not type_verified(page, "#sign-in-code", code, 0.18, 0.30):
                print("вход: код не принят -> перезагрузка", flush=True)
                continue

            page.wait_for_timeout(700)
            try:
                page.keyboard.press("Enter")
            except Exception:
                page.keyboard.press("Enter")
            for _ in range(25):
                page.wait_for_timeout(1000)
                try:
                    if page.locator("input[type=password]").count() > 0:
                        break
                    if page.locator("#sign-in-code").count() == 0:
                        break
                except Exception:
                    break
            print("вход: после кода", page.url, flush=True)
            try:
                if page.locator("#sign-in-code").count() > 0 or page.locator("text=/LOG IN BY QR CODE/i").count() > 0:
                    print("вход: Telegram не принял код -> перезагрузка", flush=True)
                    continue
            except Exception:
                pass
            ok = True
            break

        if not ok:
            print("вход: три попытки не удались", flush=True)
            return False

        if page.locator("input[type=password]").count() > 0:
            pwd = find_password(account_id, phone)
            print("вход: 2FA пароль найден:", bool(pwd), flush=True)
            if pwd:
                if type_verified(page, "input[type=password]", pwd):
                    page.wait_for_timeout(500)
                    try:
                        page.keyboard.press("Enter")
                    except Exception:
                        page.keyboard.press("Enter")
                    page.wait_for_timeout(7000)
                    print("вход: после пароля", page.url, flush=True)
                else:
                    print("вход: пароль не ввёлся", flush=True)
            else:
                print("вход: ВПИШИ ПАРОЛЬ В ОКНЕ, жду до 3 минут", flush=True)
                waited = 0
                while waited < 180:
                    page.wait_for_timeout(2000)
                    waited += 2
                    try:
                        if page.locator("input[type=password]").count() == 0:
                            break
                    except Exception:
                        break
                print("вход: пароль введён вручную", page.url, flush=True)

        try:
            page.goto("https://web.telegram.org/k/#@PremiumBot",
                      wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(8000)
            print("вход: PremiumBot", page.url, flush=True)
            for pat in ["text=/^START$/i", "text=/^ЗАПУСТИТЬ$/i", "button:has-text('START')"]:
                try:
                    page.locator(pat).first.click(timeout=6000)
                    print("вход: START нажат", flush=True)
                    break
                except Exception:
                    continue
        except Exception as exc:
            print("вход: бот fail", exc.__class__.__name__, flush=True)

        return True




