"""Клиент Local API Окто + мок для запуска без браузера.

Пути эндпоинтов вынесены в PATHS: у разных версий Окто они могут отличаться,
правится в одном месте.
"""
from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

PATHS = {
    "create": "/api/v1/profiles",
    "start": "/api/v1/profiles/{profile_id}/start",
    "stop": "/api/v1/profiles/{profile_id}/stop",
    "delete": "/api/v1/profiles/{profile_id}",
    "list": "/api/v1/profiles",
}


@dataclass
class StartedProfile:
    profile_id: str
    ws_url: str = ""


class OctoClient:
    """Реальный Окто на 127.0.0.1:58888."""

    def __init__(self, base_url: str, token: str = "", timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = {"Content-Type": "application/json"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def _url(self, key: str, profile_id: str = "") -> str:
        path = PATHS[key].format(profile_id=profile_id)
        return f"{self.base_url}{path}"

    def create_profile(self, name: str, proxy: dict[str, str], fingerprint: dict[str, Any]) -> str:
        body = {
            "name": name,
            "proxy": {
                "type": proxy.get("scheme", "http"),
                "host": proxy.get("host", ""),
                "port": int(proxy.get("port", 0)),
                "username": proxy.get("username", ""),
                "password": proxy.get("password", ""),
            },
            "fingerprint": {
                "user_agent": fingerprint.get("ua", ""),
                "platform": fingerprint.get("platform", ""),
                "screen": fingerprint.get("screen", [1920, 1080]),
                "device_scale_factor": fingerprint.get("dpr", 1),
                "timezone": fingerprint.get("timezone", ""),
                "locale": fingerprint.get("language", "en-US"),
            },
        }
        with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
            response = client.post(self._url("create"), json=body)
            response.raise_for_status()
            data = response.json()
        return str(data.get("id") or data.get("data", {}).get("id") or "")

    def start_profile(self, profile_id: str) -> StartedProfile:
        with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
            response = client.get(self._url("start", profile_id))
            response.raise_for_status()
            data = response.json()

        ws_url = str(
            data.get("ws")
            or data.get("debug_port")
            or data.get("data", {}).get("ws", "")
            or ""
        )
        return StartedProfile(profile_id=profile_id, ws_url=ws_url)

    def stop_profile(self, profile_id: str) -> None:
        with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
            client.get(self._url("stop", profile_id))

    def delete_profile(self, profile_id: str) -> None:
        with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
            client.delete(self._url("delete", profile_id))

    def alive_ids(self) -> list[str]:
        """ID профилей, которые сейчас реально запущены."""
        try:
            with httpx.Client(timeout=10.0, headers=self.headers) as client:
                response = client.get(self._url("list"), params={"limit": 500})
                response.raise_for_status()
                data = response.json()
        except Exception:  # noqa: BLE001 — Окто мог не ответить, значит живыми считаем только известные
            return list(_known_alive.keys())

        items = data if isinstance(data, list) else data.get("data", data.get("profiles", []))
        alive: list[str] = []
        for item in items:
            status = str(item.get("status", "")).lower()
            if status in {"running", "started", "active"}:
                alive.append(str(item.get("id", "")))
        return [pid for pid in alive if pid]

    # --- служебное для merge-режима ---
    def mark_alive(self, profile_id: str) -> None:
        _known_alive[profile_id] = time.time()

    def mark_dead(self, profile_id: str) -> None:
        _known_alive.pop(profile_id, None)


_known_alive: dict[str, float] = {}


class MockOcto(OctoClient):
    """Заглушка: окна живут сами и закрываются по таймеру.

    Нужна, чтобы прогнать логику слотов без Окто и без ОЗУ.
    """

    def __init__(self) -> None:
        super().__init__("mock://")
        self.ttl = float(os.getenv("TWKS_MOCK_WINDOW_TTL", "25"))
        self._created: dict[str, float] = {}

    def create_profile(self, name: str, proxy: dict[str, str], fingerprint: dict[str, Any]) -> str:
        profile_id = f"mock_{uuid.uuid4().hex[:10]}"
        self._created[profile_id] = 0.0
        return profile_id

    def start_profile(self, profile_id: str) -> StartedProfile:
        self._created[profile_id] = time.time()
        return StartedProfile(profile_id=profile_id, ws_url="")

    def stop_profile(self, profile_id: str) -> None:
        self._created.pop(profile_id, None)

    def delete_profile(self, profile_id: str) -> None:
        self._created.pop(profile_id, None)

    def alive_ids(self) -> list[str]:
        now = time.time()
        alive = []
        for profile_id, started_at in list(self._created.items()):
            if started_at and (now - started_at) > self.ttl:
                self._created.pop(profile_id, None)  # окно «закрылось»
                continue
            alive.append(profile_id)
        return alive
