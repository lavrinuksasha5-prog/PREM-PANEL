"""Слоты — жёсткий потолок одновременных окон.

Инвариант: занятых слотов никогда не больше settings.max_slots.
Проверка и захват — под одним локом, иначе два одновременных клика
протащат три окна.
"""
from __future__ import annotations

import threading

from sqlalchemy.orm import Session

from .config import settings
from .models import Account, Slot, SlotState

_lock = threading.Lock()


def busy_count(db: Session) -> int:
    return db.query(Slot).filter(Slot.state != SlotState.FREE).count()


def free_count(db: Session) -> int:
    return max(0, settings.max_slots - busy_count(db))


def reserve(db: Session, account: Account) -> Slot | None:
    """Пытается занять слот под аккаунт. None = мест нет."""
    with _lock:
        if busy_count(db) >= settings.max_slots:
            return None

        slot = (
            db.query(Slot)
            .filter(Slot.state == SlotState.FREE)
            .order_by(Slot.id)
            .first()
        )
        if slot is None:
            return None

        slot.state = SlotState.RESERVED
        slot.account_id = account.id
        slot.profile_id = ""

        account.slot_no = slot.id
        db.commit()
        return slot


def mark_busy(db: Session, slot_id: int, profile_id: str) -> None:
    slot = db.get(Slot, slot_id)
    if not slot:
        return
    slot.state = SlotState.BUSY
    slot.profile_id = profile_id or ""
    db.commit()


def release(db: Session, slot_id: int) -> None:
    with _lock:
        slot = db.get(Slot, slot_id)
        if not slot:
            return
        slot.state = SlotState.FREE
        slot.account_id = None
        slot.profile_id = ""
        db.commit()


def release_by_account(db: Session, account: Account) -> None:
    if not account.slot_no:
        return
    release(db, account.slot_no)
    account.slot_no = 0


def held_profile_ids(db: Session) -> dict[str, int]:
    """profile_id -> slot_no для всех занятых слотов."""
    rows = db.query(Slot).filter(Slot.state != SlotState.FREE).all()
    return {row.profile_id: row.id for row in rows if row.profile_id}
