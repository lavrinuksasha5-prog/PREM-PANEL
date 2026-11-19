"""Таблицы и состояния аккаунтов."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class AccountState:
    """Состояния аккаунта. Переходы — только через API панели."""

    PARSED = "parsed"            # нашли в архиве, прокси ещё не проверяли
    CHECKING = "checking"        # проверяем прокси/сессию
    READY = "ready"              # готов к открытию
    PROXY_FAIL = "proxy_fail"    # прокси не поднялся
    OPENING = "opening"          # слот занят, агент создаёт профиль
    IN_ACCOUNT = "in_account"    # окно живо, аккаунт внутри
    DONE = "done"                # окно закрыто, сессия снята
    FAILED = "failed"            # ошибка, можно повторить

    ALL = [PARSED, CHECKING, READY, PROXY_FAIL, OPENING, IN_ACCOUNT, DONE, FAILED]


class SlotState:
    FREE = "free"
    RESERVED = "reserved"   # слот закреплён, профиль ещё создаётся
    BUSY = "busy"           # окно живо


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    proxy_count: Mapped[int] = mapped_column(Integer, default=0)
    account_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), index=True)

    phone: Mapped[str] = mapped_column(String(64), default="")
    tg_name: Mapped[str] = mapped_column(String(255), default="")
    premium: Mapped[bool] = mapped_column(Boolean, default=False)
    country: Mapped[str] = mapped_column(String(8), default="")

    state: Mapped[str] = mapped_column(String(32), default=AccountState.PARSED, index=True)
    error: Mapped[str] = mapped_column(Text, default="")

    # путь к папке tdata внутри архива
    tdata_key: Mapped[str] = mapped_column(String(512), default="")

    # прокси: импорт (проверка партии) и веб (вход в окно) — разные
    proxy_import: Mapped[str] = mapped_column(Text, default="")
    proxy_web: Mapped[str] = mapped_column(Text, default="")

    fingerprint: Mapped[str] = mapped_column(Text, default="")  # JSON карточки устройства
    profile_id: Mapped[str] = mapped_column(String(128), default="")
    slot_no: Mapped[int] = mapped_column(Integer, default=0)

    session_blob: Mapped[str] = mapped_column(Text, default="")  # зашифрованная сессия
    session_saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Slot(Base):
    __tablename__ = "slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state: Mapped[str] = mapped_column(String(16), default=SlotState.FREE)
    account_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    profile_id: Mapped[str] = mapped_column(String(128), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    level: Mapped[str] = mapped_column(String(16), default="info")
    code: Mapped[str] = mapped_column(String(64), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgentCommand(Base):
    __tablename__ = "agent_commands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    kind: Mapped[str] = mapped_column(String(32))
    payload: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    result: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
