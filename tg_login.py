import asyncio, random, re, shutil, threading, time

PRE = "380 375 995 996 998 994 992 971 972 966 90 7 1 20 27 30 31 33 34 36 39 40 41 43 44 45 46 47 48 49 51 52 53 54 55 56 57 58 60 61 62 63 64 65 66 81 82 84 86 91 92 93 94 95 98".split()
PRE = sorted(PRE, key=len, reverse=True)


def split_phone(ph):
    for p in PRE:
        if ph.startswith(p):
            return p, ph[len(p):]
    return ph[:2], ph[2:]


def wait_any(page, sels, timeout=20000):
    end = time.time() + timeout / 1000.0
    while time.time() < end:
        for s in sels:
            try:
                if page.locator(s).count() > 0:
                    return s
            except Exception:
                pass
        time.sleep(0.3)
    return ""


def alive_page(ctx, old):
    try:
        if old is not None and not old.is_closed():
            return old
    except Exception:
        pass
    pages = []
    try:
        pages = [p for p in ctx.pages if not p.is_closed()]
    except Exception:
        pages = []
    tg = [p for p in pages if "web.telegram.org" in (p.url or "")]
    keep = tg[0] if tg else None
    for p in pages:
        if p is not keep:
            try:
                p.close()
            except Exception:
                pass
    if keep is not None:
        try:
            keep.bring_to_front()
        except Exception:
            pass
        return keep
    page = ctx.new_page()
    try:
        page.bring_to_front()
    except Exception:
        pass
    return page


def clear_and_type(page, sel, text, lo=0.06, hi=0.12):
    try:
        page.locator(sel).first.wait_for(state="visible", timeout=15000)
        page.eval_on_selector(sel, "el => { el.focus(); }")
        page.wait_for_timeout(300)
        for _ in range(len(str(text)) + 18):
            page.keyboard.press("Backspace")
            time.sleep(0.015)
        for ch in str(text):
            page.keyboard.type(ch)
            time.sleep(random.uniform(lo, hi))
        page.wait_for_timeout(500)
        got = (page.input_value(sel) or "").replace(" ", "").replace("+", "")
        want = str(text).replace("+", "").replace(" ", "")
        return want in got
    except Exception as exc:
        print("ввод fail:", exc.__class__.__name__, flush=True)
        return False


def press_next(page, tries=14):
    for _ in range(tries):
        page.wait_for_timeout(400)
        try:
            b = page.locator("button.btn-primary").first
            if b.is_visible() and b.is_enabled():
                b.click(timeout=4000)
                return True
        except Exception:
            pass
    try:
        page.keyboard.press("Enter")
        return True
    except Exception:
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
                v = data.get(key)
                if isinstance(v, str) and v.strip():
                    return v.strip()
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
    return ""


def first_present(page, sels):
    for s in sels:
        try:
            if page.locator(s).count() > 0:
                return s
        except Exception:
            pass
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
        page = alive_page(ctx, None)

        for attempt in range(1, 4):
            page = alive_page(ctx, page)
            since = time.time()
            print("вход: попытка", attempt, flush=True)

            try:
                url = "https://web.telegram.org/k/"
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
            except Exception as exc:
                print("вход: goto", exc.__class__.__name__, flush=True)

            if not wait_any(page, ["#sign-in-phone-number", "input.input-field-input"], 7000):
                try:
                    page.evaluate("""() => {
                        const els = [...document.querySelectorAll('button,a,div')];
                        const el = els.find(e => e.offsetParent && /LOG IN BY PHONE NUMBER|номеру телефона/i.test(e.textContent || ''));
                        if (el) el.click();
                    }""")
                    print("вход: клик по номеру (js)", flush=True)
                except Exception as exc:
                    print("вход: клик js fail", exc.__class__.__name__, flush=True)
                wait_any(page, ["#sign-in-phone-number", "input.input-field-input"], 15000)

            if not wait_any(page, ["#sign-in-phone-number", "input.input-field-input"], 15000):
                print("вход: формы нет -> новая попытка", flush=True)
                continue

            box = {}

            def grab():
                try:
                    box["code"] = asyncio.run(wait_code(account_id, 200, since))
                except Exception as exc:
                    box["err"] = str(exc)

            th = threading.Thread(target=grab, daemon=True)
            th.start()

            phone_sel = first_present(page, ["#sign-in-phone-number", "input.input-field-input", "input[type=tel]"])
            if not phone_sel or not clear_and_type(page, phone_sel, "+" + phone):
                print("вход: номер не лёг -> новая попытка", flush=True)
                continue
            print("вход: номер введён", flush=True)

            press_next(page)
            print("вход: жду поле кода...", flush=True)

            if not wait_any(page, ["#sign-in-code", "input.input-field-input"], 35000):
                print("вход: поле кода не появилось", flush=True)
                continue

            th.join(timeout=120)
            code = box.get("code", "")
            print("вход: код", code or "нет", flush=True)
            if not code:
                continue

            code_sel = first_present(page, ["#sign-in-code", "input.input-field-input", "input[type=text]"])
            if not code_sel or not clear_and_type(page, code_sel, code, 0.07, 0.13):
                print("вход: код не лёг", flush=True)
                continue
            press_next(page)
            print("вход: код отправлен", flush=True)

            has_pass = False
            for _ in range(25):
                page.wait_for_timeout(1000)
                try:
                    if page.locator("input[type=password]").count() > 0:
                        has_pass = True
                        break
                    if page.locator("#sign-in-code").count() == 0:
                        break
                except Exception:
                    break

            if has_pass:
                pwd = find_password(account_id, phone)
                print("вход: пароль найден:", bool(pwd), flush=True)
                if pwd:
                    done = False
                    for sel in ["#sign-in-password", "input[type=password]", "input[name=password]"]:
                        if clear_and_type(page, sel, pwd, 0.05, 0.1):
                            print("вход: пароль введён в", sel, flush=True)
                            press_next(page)
                            page.wait_for_timeout(6000)
                            done = True
                            break
                    if not done:
                        print("вход: поле пароля не найдено", flush=True)
                else:
                    print("вход: ВПИШИ ПАРОЛЬ В ОКНЕ, жду до 3 минут", flush=True)
                    w = 0
                    while w < 180:
                        page.wait_for_timeout(2000)
                        w += 2
                        try:
                            if page.locator("input[type=password]").count() == 0:
                                break
                        except Exception:
                            break

            try:
                if page.locator("input[type=password]").count() > 0:
                    print("вход: пароль не принят", flush=True)
                    continue
            except Exception:
                pass

            print("вход: успешно", page.url, flush=True)
            ok = True
            break

        if not ok:
            print("вход: не удалось за 3 попытки", flush=True)
            return False

        try:
            page.goto("https://web.telegram.org/k/#@PremiumBot", wait_until="domcontentloaded", timeout=45000)
            wait_any(page, ["text=/Premium/i"], 15000)
            page.wait_for_timeout(2500)
            print("вход: PremiumBot", page.url, flush=True)
            for pat in ["text=/^START$/i", "text=/^ЗАПУСТИТЬ$/i"]:
                try:
                    page.locator(pat).first.click(timeout=5000)
                    print("вход: START нажат", flush=True)
                    break
                except Exception:
                    continue
        except Exception as exc:
            print("вход: бот", exc.__class__.__name__, flush=True)
        return True





