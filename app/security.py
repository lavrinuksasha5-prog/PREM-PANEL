"""Авторизация админа и шифрование сессий аккаунтов."""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import settings


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt="twks")


def make_session_cookie() -> str:
    return _serializer().dumps({"u": "admin"})


def verify_session_cookie(value: str | None) -> bool:
    if not value:
        return False
    try:
        _serializer().loads(value, max_age=settings.session_ttl)
        return True
    except (BadSignature, SignatureExpired):
        return False


def require_admin(request: Request) -> None:
    if not verify_session_cookie(request.cookies.get(settings.cookie_name)):
        raise HTTPException(status_code=401, detail="Требуется вход в панель")


def require_agent(request: Request) -> None:
    if request.headers.get("X-Agent-Token", "") != settings.agent_token:
        raise HTTPException(status_code=401, detail="Неверный токен агента")


def _fernet() -> Fernet:
    # ключ выводим из секрета панели — отдельный файл не нужен
    digest = hashlib.sha256(settings.secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_text(value: str) -> str:
    if not value:
        return ""
    return _fernet().encrypt(value.encode()).decode()


def decrypt_text(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        return ""
