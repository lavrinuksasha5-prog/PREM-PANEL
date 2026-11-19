"""Парсинг и проверка прокси.

Поддерживаем форматы:
  host:port
  host:port:user:pass
  user:pass@host:port
  scheme://user:pass@host:port
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass
class Proxy:
    raw: str
    scheme: str = "http"
    host: str = ""
    port: int = 0
    username: str = ""
    password: str = ""

    @property
    def url(self) -> str:
        auth = ""
        if self.username:
            auth = f"{self.username}:{self.password}@"
        return f"{self.scheme}://{auth}{self.host}:{self.port}"


def parse_proxy(line: str) -> Proxy | None:
    line = line.strip()
    if not line:
        return None

    scheme = "http"
    if "://" in line:
        scheme, line = line.split("://", 1)

    # user:pass@host:port
    if "@" in line:
        creds, hostport = line.rsplit("@", 1)
        user, _, password = creds.partition(":")
        host, _, port = hostport.rpartition(":")
        if not host or not port.isdigit():
            return None
        return Proxy(raw=line, scheme=scheme, host=host, port=int(port), username=user, password=password)

    parts = line.split(":")
    if len(parts) == 2 and parts[1].isdigit():
        return Proxy(raw=line, scheme=scheme, host=parts[0], port=int(parts[1]))
    if len(parts) == 4 and parts[1].isdigit() and parts[3].isdigit():
        return Proxy(raw=line, scheme=scheme, host=parts[0], port=int(parts[1]),
                     username=parts[2], password=parts[3])
    return None


def parse_proxy_list(text: str) -> list[Proxy]:
    result: list[Proxy] = []
    for line in text.replace(",", "\n").splitlines():
        proxy = parse_proxy(line)
        if proxy:
            result.append(proxy)
    return result


def check_proxy(proxy: Proxy, timeout: float = 10.0) -> dict:
    """Проверяет прокси запросом к ip-эхо. Никогда не бросает наружу."""
    try:
        with httpx.Client(proxy=proxy.url, timeout=timeout, verify=False) as client:
            response = client.get("https://api.ipify.org?format=json")
            response.raise_for_status()
            ip = response.json().get("ip", "")
            return {"ok": True, "ip": ip, "error": ""}
    except Exception as exc:  # noqa: BLE001 — любая сетевая ошибка = прокси мёртв
        return {"ok": False, "ip": "", "error": str(exc)[:300]}
