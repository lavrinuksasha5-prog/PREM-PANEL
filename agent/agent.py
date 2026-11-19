"""Агент на ПК: сам стучится в панель, выполняет команды в Окто.

Запуск:
    TWKS_PANEL_URL=http://127.0.0.1:8000 python agent/agent.py
"""
from __future__ import annotations

import json
import os
import time
import traceback
from typing import Any

import httpx

from octo import MockOcto, OctoClient

PANEL_URL = os.getenv("TWKS_PANEL_URL", "http://127.0.0.1:8000").rstrip("/")
AGENT_TOKEN = os.getenv("TWKS_AGENT_TOKEN", "agent-secret")
AGENT_ID = os.getenv("TWKS_AGENT_ID", "default")
POLL_INTERVAL = float(os.getenv("TWKS_AGENT_POLL", "2"))
OCTO_MOCK = os.getenv("TWKS_OCTO_MOCK", "true").strip().lower() in {"1", "true", "yes", "on"}

HEADERS = {"X-Agent-Token": AGENT_TOKEN, "Content-Type": "application/json"}

# profile_id -> {"account_id": int, "proxy": dict, "name": str}
PROFILES: dict[str, dict[str, Any]] = {}


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def build_octo() -> OctoClient:
    if OCTO_MOCK:
        log("Окто в мок-режиме: окна эмулируются таймером")
        return MockOcto()
    return OctoClient(
        base_url=os.getenv("TWKS_OCTO_BASE_URL", "http://127.0.0.1:58888"),
        token=os.getenv("TWKS_OCTO_TOKEN", ""),
    )


def split_proxy(url: str) -> dict[str, str]:
    """proxy.url → части для API Окто."""
    scheme = "http"
    rest = url
    if "://" in rest:
        scheme, rest = rest.split("://", 1)
    auth, _, hostport = rest.rpartition("@")
    username, _, password = auth.partition(":")
    host, _, port = hostport.partition(":")
    return {
        "scheme": scheme,
        "host": host,
        "port": port,
        "username": username,
        "password": password,
    }


# ------------------------------------------------------------------ сессия


def dump_session(ws_url: str) -> dict[str, Any] | None:
    """Снимает cookies + localStorage через CDP. None = не удалось/нет playwright."""
    if not ws_url:
        return None
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("playwright не установлен — сессию снять нечем")
        return None

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(ws_url)
            contexts = browser.contexts
            context = contexts[0] if contexts else browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()

            if "web.telegram.org" not in page.url:
                page.goto("https://web.telegram.org/a/", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(4000)

            local = page.evaluate("() => Object.fromEntries(Object.entries(localStorage))")
            cookies = context.cookies()

            logged_in = any("auth_key" in key.lower() or key == "user_auth" for key in local)
            if not logged_in:
                log("в окне ещё нет авторизации — сессию не снимаю")
                return None

            return {
                "version": 1,
                "exported_at": int(time.time()),
                "url": page.url,
                "user_agent": page.evaluate("() => navigator.userAgent"),
                "cookies": cookies,
                "origins": [{"origin": "https://web.telegram.org", "localStorage": local}],
            }
    except Exception:  # noqa: BLE001
        log(f"dump_session упал: {traceback.format_exc(limit=2)}")
        return None


# ------------------------------------------------------------------ команды


def handle_open(octo: OctoClient, payload: dict[str, Any]) -> dict[str, Any]:
    account_id = payload.get("account_id")
    proxy = split_proxy(payload.get("proxy", ""))
    fingerprint = payload.get("fingerprint", {})
    name = payload.get("profile_name", f"twks_{account_id}")

    try:
        profile_id = octo.create_profile(name, proxy, fingerprint)
        if not profile_id:
            return {"ok": False, "account_id": account_id, "error": "Окто не вернул id профиля"}

        started = octo.start_profile(profile_id)
        PROFILES[profile_id] = {"account_id": account_id, "proxy": proxy, "name": name}

        if isinstance(octo, MockOcto):
            # мок: ждём «логин», сессию не отдаём
            return {"ok": True, "account_id": account_id, "profile_id": profile_id, "session": None}

        session = dump_session(started.ws_url)
        return {"ok": True, "account_id": account_id, "profile_id": profile_id, "session": session}
    except Exception as exc:  # noqa: BLE001
        log(f"open_profile #{account_id}: {exc}")
        return {"ok": False, "account_id": account_id, "error": str(exc)[:500]}


def handle_close(octo: OctoClient, payload: dict[str, Any]) -> dict[str, Any]:
    profile_id = str(payload.get("profile_id", ""))
    if not profile_id:
        return {"ok": True, "skipped": True}
    try:
        octo.stop_profile(profile_id)
        octo.delete_profile(profile_id)
        PROFILES.pop(profile_id, None)
        return {"ok": True, "profile_id": profile_id}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "profile_id": profile_id, "error": str(exc)[:500]}


def handle_dump(octo: OctoClient, payload: dict[str, Any]) -> dict[str, Any]:
    profile_id = str(payload.get("profile_id", ""))
    ws_url = str(payload.get("ws_url", ""))
    session = dump_session(ws_url) if not isinstance(octo, MockOcto) else None
    return {
        "ok": bool(session),
        "account_id": payload.get("account_id"),
        "profile_id": profile_id,
        "session": session,
        "error": "" if session else "нет авторизации в окне",
    }


def run_command(octo: OctoClient, command: dict[str, Any]) -> None:
    kind = command.get("kind")
    payload = command.get("payload", {})
    log(f"команда {kind} → {json.dumps(payload, ensure_ascii=False)[:160]}")

    if kind == "open_profile":
        result = handle_open(octo, payload)
    elif kind == "close_profile":
        result = handle_close(octo, payload)
    elif kind == "dump_session":
        result = handle_dump(octo, payload)
    else:
        result = {"ok": False, "error": f"неизвестная команда {kind}"}

    report(command["id"], "done" if result.get("ok") else "error", result)


def report(command_id: int, status: str, result: dict[str, Any]) -> None:
    try:
        with httpx.Client(timeout=15.0, headers=HEADERS) as client:
            client.post(f"{PANEL_URL}/api/agent/result", json={
                "command_id": command_id,
                "status": status,
                "result": result,
            })
    except Exception:  # noqa: BLE001
        log(f"не смог отправить результат команды {command_id}")


# ------------------------------------------------------------------ цикл


def main() -> None:
    octo = build_octo()
    log(f"агент {AGENT_ID} → панель {PANEL_URL}")

    while True:
        try:
            alive = octo.alive_ids()
            with httpx.Client(timeout=15.0, headers=HEADERS) as client:
                response = client.post(f"{PANEL_URL}/api/agent/poll", json={
                    "agent_id": AGENT_ID,
                    "alive": alive,
                })
            if response.status_code == 401:
                log("панель отвергла токен агента — проверь TWKS_AGENT_TOKEN")
                time.sleep(10)
                continue
            response.raise_for_status()
            for command in response.json().get("commands", []):
                run_command(octo, command)
        except httpx.HTTPError as exc:
            log(f"панель недоступна: {exc}")
        except Exception:  # noqa: BLE001
            log(traceback.format_exc(limit=3))

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
