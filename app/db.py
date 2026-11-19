"""Подключение к базе и создание слотов."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings
from .models import Base, Slot, SlotState

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db(max_slots: int) -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        existing = {s.id for s in db.query(Slot).all()}
        for i in range(1, max_slots + 1):
            if i not in existing:
                db.add(Slot(id=i, state=SlotState.FREE))
        # лимит уменьшили — лишние свободные слоты убираем
        for slot in db.query(Slot).filter(Slot.id > max_slots).all():
            if slot.state == SlotState.FREE:
                db.delete(slot)
        db.commit()


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
