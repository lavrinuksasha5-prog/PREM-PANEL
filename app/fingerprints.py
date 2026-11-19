"""Каталог карточек устройств.

Правило: карточка связна внутри себя (UA ↔ экран ↔ GPU ↔ платформа).
Рандом по отдельным полям запрещён — получается несовместимый «франкенштейн».
"""
from __future__ import annotations

import hashlib
from typing import Any

# weight — как часто модель встречается у живых людей
CATALOG: list[dict[str, Any]] = [
    {
        "id": "redmi_note10pro",
        "model": "Redmi Note 10 Pro",
        "ua": "Mozilla/5.0 (Linux; Android 13; 2201117TG) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "platform": "Linux armv8l",
        "screen": [1080, 2400],
        "dpr": 2.75,
        "gpu_vendor": "Qualcomm",
        "gpu_renderer": "Adreno (TM) 618",
        "cores": 8,
        "memory": 6,
        "touch": 5,
        "weight": 18,
    },
    {
        "id": "redmi_9a",
        "model": "Redmi 9A",
        "ua": "Mozilla/5.0 (Linux; Android 10; M2006C3LG) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36",
        "platform": "Linux aarch64",
        "screen": [720, 1600],
        "dpr": 2.0,
        "gpu_vendor": "Imagination Technologies",
        "gpu_renderer": "PowerVR Rogue GE8320",
        "cores": 8,
        "memory": 4,
        "touch": 5,
        "weight": 10,
    },
    {
        "id": "poco_x3pro",
        "model": "POCO X3 Pro",
        "ua": "Mozilla/5.0 (Linux; Android 12; M2102J20SG) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",
        "platform": "Linux armv8l",
        "screen": [1080, 2400],
        "dpr": 2.75,
        "gpu_vendor": "Qualcomm",
        "gpu_renderer": "Adreno (TM) 640",
        "cores": 8,
        "memory": 6,
        "touch": 5,
        "weight": 8,
    },
    {
        "id": "xiaomi_12",
        "model": "Xiaomi 12",
        "ua": "Mozilla/5.0 (Linux; Android 13; 2201123G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
        "platform": "Linux armv8l",
        "screen": [1080, 2400],
        "dpr": 2.75,
        "gpu_vendor": "Qualcomm",
        "gpu_renderer": "Adreno (TM) 730",
        "cores": 8,
        "memory": 8,
        "touch": 5,
        "weight": 5,
    },
    {
        "id": "xiaomi_13t",
        "model": "Xiaomi 13T",
        "ua": "Mozilla/5.0 (Linux; Android 14; 2306EPN60G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
        "platform": "Linux armv8l",
        "screen": [1220, 2712],
        "dpr": 2.75,
        "gpu_vendor": "ARM",
        "gpu_renderer": "Mali-G610 MC6",
        "cores": 8,
        "memory": 8,
        "touch": 5,
        "weight": 4,
    },
    {
        "id": "samsung_a54",
        "model": "Samsung Galaxy A54",
        "ua": "Mozilla/5.0 (Linux; Android 14; SM-A546B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36",
        "platform": "Linux armv8l",
        "screen": [1080, 2340],
        "dpr": 2.625,
        "gpu_vendor": "ARM",
        "gpu_renderer": "Mali-G68 MP5",
        "cores": 8,
        "memory": 6,
        "touch": 5,
        "weight": 12,
    },
    {
        "id": "samsung_s23",
        "model": "Samsung Galaxy S23",
        "ua": "Mozilla/5.0 (Linux; Android 14; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
        "platform": "Linux armv8l",
        "screen": [1080, 2340],
        "dpr": 2.8125,
        "gpu_vendor": "Qualcomm",
        "gpu_renderer": "Adreno (TM) 740",
        "cores": 8,
        "memory": 8,
        "touch": 5,
        "weight": 4,
    },
    {
        "id": "meizu_20",
        "model": "Meizu 20",
        "ua": "Mozilla/5.0 (Linux; Android 13; M2381) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",
        "platform": "Linux armv8l",
        "screen": [1080, 2400],
        "dpr": 2.75,
        "gpu_vendor": "Qualcomm",
        "gpu_renderer": "Adreno (TM) 740",
        "cores": 8,
        "memory": 8,
        "touch": 5,
        "weight": 3,
    },
    {
        "id": "realme_9pro",
        "model": "Realme 9 Pro",
        "ua": "Mozilla/5.0 (Linux; Android 12; RMX3461) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
        "platform": "Linux armv8l",
        "screen": [1080, 2412],
        "dpr": 2.4,
        "gpu_vendor": "Qualcomm",
        "gpu_renderer": "Adreno (TM) 619",
        "cores": 8,
        "memory": 6,
        "touch": 5,
        "weight": 7,
    },
    {
        "id": "oneplus_nord2",
        "model": "OnePlus Nord 2",
        "ua": "Mozilla/5.0 (Linux; Android 12; DN2103) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "platform": "Linux armv8l",
        "screen": [1080, 2400],
        "dpr": 2.75,
        "gpu_vendor": "ARM",
        "gpu_renderer": "Mali-G77 MC9",
        "cores": 8,
        "memory": 8,
        "touch": 5,
        "weight": 4,
    },
    {
        "id": "pixel_7",
        "model": "Google Pixel 7",
        "ua": "Mozilla/5.0 (Linux; Android 14; GVU6C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
        "platform": "Linux armv8l",
        "screen": [1080, 2400],
        "dpr": 2.625,
        "gpu_vendor": "ARM",
        "gpu_renderer": "Mali-G710 MP7",
        "cores": 8,
        "memory": 8,
        "touch": 5,
        "weight": 3,
    },
    {
        "id": "iphone_13",
        "model": "iPhone 13",
        "ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
        "platform": "iPhone",
        "screen": [1170, 2532],
        "dpr": 3.0,
        "gpu_vendor": "Apple",
        "gpu_renderer": "Apple GPU",
        "cores": 6,
        "memory": 4,
        "touch": 5,
        "weight": 6,
    },
]

# страна IP → язык и таймзона. Прокси-гео должно совпадать с этой строкой
LOCALE_BY_COUNTRY: dict[str, dict[str, str]] = {
    "UA": {"language": "uk-UA", "timezone": "Europe/Kiev", "currency": "UAH"},
    "RU": {"language": "ru-RU", "timezone": "Europe/Moscow", "currency": "RUB"},
    "KZ": {"language": "ru-RU", "timezone": "Asia/Almaty", "currency": "KZT"},
    "BY": {"language": "ru-RU", "timezone": "Europe/Minsk", "currency": "BYN"},
    "PL": {"language": "pl-PL", "timezone": "Europe/Warsaw", "currency": "PLN"},
    "DE": {"language": "de-DE", "timezone": "Europe/Berlin", "currency": "EUR"},
    "US": {"language": "en-US", "timezone": "America/New_York", "currency": "USD"},
    "TR": {"language": "tr-TR", "timezone": "Europe/Istanbul", "currency": "TRY"},
    "GE": {"language": "ka-GE", "timezone": "Asia/Tbilisi", "currency": "GEL"},
    "AE": {"language": "ar-AE", "timezone": "Asia/Dubai", "currency": "AED"},
}


def _pick_index(seed: str, total_weight: int) -> int:
    digest = hashlib.sha256(seed.encode()).digest()
    return int.from_bytes(digest[:4], "big") % total_weight


def pick_device(seed: str | int) -> dict[str, Any]:
    """Детерминированно выбирает карточку устройства по сиду аккаунта."""
    total = sum(item["weight"] for item in CATALOG)
    point = _pick_index(str(seed), total)

    running = 0
    chosen = CATALOG[-1]
    for item in CATALOG:
        running += item["weight"]
        if point < running:
            chosen = item
            break

    card = {k: v for k, v in chosen.items() if k != "weight"}
    # мелкий шум, уникальный для аккаунта
    digest = hashlib.sha256(f"noise:{seed}".encode()).digest()
    card["canvas_noise"] = digest[0] % 256
    card["audio_noise"] = digest[1] % 256
    card["dnt"] = bool(digest[2] % 2)
    card["locale"] = ""  # заполняется из гео прокси
    return card


def locale_for_country(country: str) -> dict[str, str]:
    return LOCALE_BY_COUNTRY.get(country.upper(), {
        "language": "en-US",
        "timezone": "Europe/London",
        "currency": "USD",
    })
