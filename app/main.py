"""Панель TWKS: слоты, аккаунты, команды агенту."""
from __future__ import annotations

import hmac
import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import agent_hub
from . import slots as slot_service
from .archive import scan_zip
from .config import settings
from .db import get_db, init_db
from .fingerprints import locale_for_country, pick_device
from .models import Account, AccountState, Batch, Event, Slot, SlotState
from .proxies import check_proxy, parse_proxy, parse_proxy_list
from .security import (
    decrypt_text,
    encrypt_text,
    make_session_cookie,
    require_admin,
    require_agent,
    verify_session_cookie,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(settings.max_slots)
    yield


app = FastAPI(title="TWKS Panel", docs_url=None, redoc_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------- helpers


def add_event(db: Session, message: str, code: str = "", level: str = "info",
              account_id: int | None = None) -> None:
    db.add(Event(account_id=account_id, level=level, code=code, message=message))
    db.commit()


def account_json(account: Account) -> dict[str, Any]:
    card: dict[str, Any] = {}
    if account.fingerprint:
        try:
            card = json.loads(account.fingerprint)
        except json.JSONDecodeError:
            card = {}
    return {
        "id": account.id,
        "batch_id": account.batch_id,
        "phone": account.phone,
        "name": account.tg_name,
        "premium": account.premium,
        "country": account.country,
        "state": account.state,
        "error": account.error,
        "slot_no": account.slot_no,
        "profile_id": account.profile_id,
        "has_session": bool(account.session_blob),
        "session_saved_at": account.session_saved_at.isoformat() if account.session_saved_at else "",
        "device": card.get("model", ""),
        "proxy_web": account.proxy_web,
    }


# ---------------------------------------------------------------- ui


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


# ---------------------------------------------------------------- auth


class LoginIn(BaseModel):
    password: str


@app.post("/api/login")
def login(payload: LoginIn, response: Response) -> dict[str, bool]:
    if not hmac.compare_digest(payload.password, settings.admin_password):
        raise HTTPException(status_code=401, detail="Неверный пароль")
    response.set_cookie(
        settings.cookie_name,
        make_session_cookie(),
        httponly=True,
        samesite="lax",
        max_age=settings.session_ttl,
    )
    return {"ok": True}


@app.post("/api/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(settings.cookie_name)
    return {"ok": True}


@app.get("/api/me")
def me(request: Request) -> dict[str, bool]:
    return {"auth": verify_session_cookie(request.cookies.get(settings.cookie_name))}


# ---------------------------------------------------------------- state


@app.get("/api/state")
def state(db: Session = Depends(get_db), _: None = Depends(require_admin)) -> dict[str, Any]:
    accounts = db.query(Account).order_by(Account.id.desc()).limit(500).all()
    slot_rows = db.query(Slot).order_by(Slot.id).all()
    busy = sum(1 for s in slot_rows if s.state != SlotState.FREE)
    events = db.query(Event).order_by(Event.id.desc()).limit(60).all()

    return {
        "slots": {
            "max": settings.max_slots,
            "busy": busy,
            "free": max(0, settings.max_slots - busy),
            "items": [
                {"id": s.id, "state": s.state, "account_id": s.account_id, "profile_id": s.profile_id}
                for s in slot_rows
            ],
        },
        "agent": {"online": agent_hub.agent_online("default")},
        "accounts": [account_json(a) for a in accounts],
        "events": [
            {
                "id": e.id,
                "level": e.level,
                "code": e.code,
                "message": e.message,
                "account_id": e.account_id,
                "ts": e.created_at.isoformat() if e.created_at else "",
            }
            for e in reversed(events)
        ],
    }


# ---------------------------------------------------------------- batches


@app.post("/api/batches")
async def create_batch(
    file: UploadFile = File(...),
    proxies: str = Form(""),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Нужен .zip архив с tdata")

    proxy_list = parse_proxy_list(proxies)
    if not proxy_list:
        raise HTTPException(status_code=400, detail="Дай хотя бы один рабочий прокси для этой партии")

    stored = settings.data_dir / "archives" / f"{uuid.uuid4().hex}.zip"
    stored.write_bytes(await file.read())

    try:
        entries = scan_zip(stored)
    except Exception as exc:  # noqa: BLE001
        stored.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Архив не читается: {exc}") from exc

    if not entries:
        stored.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="В архиве не нашёл ни одной папки tdata")

    batch = Batch(name=file.filename, proxy_count=len(proxy_list), account_count=len(entries))
    db.add(batch)
    db.flush()

    for index, entry in enumerate(entries):
        proxy = proxy_list[index % len(proxy_list)]
        db.add(Account(
            batch_id=batch.id,
            tdata_key=entry.key,
            proxy_import=proxy.raw,
            state=AccountState.PARSED,
        ))

    db.commit()
    add_event(db, f"Партия «{file.filename}»: найдено {len(entries)} tdata, прокси {len(proxy_list)}", code="batch_created")

    return {"batch_id": batch.id, "found": len(entries), "proxies": len(proxy_list)}


# ---------------------------------------------------------------- accounts


@app.post("/api/accounts/{account_id}/check")
def check_account(account_id: int, db: Session = Depends(get_db), _: None = Depends(require_admin)) -> dict[str, Any]:
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")

    proxy = parse_proxy(account.proxy_import)
    if not proxy:
        account.state = AccountState.PROXY_FAIL
        account.error = "Прокси импорта не распознан"
        db.commit()
        return {"ok": False, "error": account.error}

    account.state = AccountState.CHECKING
    db.commit()

    result = check_proxy(proxy)
    if result["ok"]:
        account.state = AccountState.READY
        account.error = ""
        add_event(db, f"Аккаунт #{account.id}: прокси живой, IP {result['ip']}", code="proxy_ok", account_id=account.id)
    else:
        account.state = AccountState.PROXY_FAIL
        account.error = result["error"]
        add_event(db, f"Аккаунт #{account.id}: прокси мёртв", code="proxy_dead", level="error", account_id=account.id)
    db.commit()
    return {"ok": result["ok"], "ip": result["ip"], "error": result["error"]}


class OpenIn(BaseModel):
    proxy: str = ""


@app.post("/api/accounts/{account_id}/open")
def open_account(account_id: int, payload: OpenIn,
                 db: Session = Depends(get_db), _: None = Depends(require_admin)) -> dict[str, Any]:
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")

    if account.state in (AccountState.OPENING, AccountState.IN_ACCOUNT):
        raise HTTPException(status_code=409, detail="Этот аккаунт уже запущен")

    if not agent_hub.agent_online("default"):
        raise HTTPException(status_code=409, detail="Агент на ПК офлайн — окно открыть некому")

    proxy_raw = payload.proxy.strip() or account.proxy_web or account.proxy_import
    proxy = parse_proxy(proxy_raw)
    if not proxy:
        raise HTTPException(status_code=409, detail="Нет прокси для входа в окно")

    # ЖЁСТКИЙ ПОТОЛОК: проверка и захват под одним локом
    slot = slot_service.reserve(db, account)
    if slot is None:
        raise HTTPException(
            status_code=409,
            detail=f"Нет свободных слотов: {slot_service.busy_count(db)}/{settings.max_slots} занято",
        )

    if not account.fingerprint:
        card = pick_device(account.id)
        if account.country:
            card.update(locale_for_country(account.country))
        account.fingerprint = json.dumps(card, ensure_ascii=False)

    account.proxy_web = proxy_raw
    account.state = AccountState.OPENING
    account.error = ""
    db.commit()

    agent_hub.enqueue(db, "open_profile", {
        "account_id": account.id,
        "slot": slot.id,
        "profile_name": f"twks_{account.batch_id}_{account.id}_{slot.id}",
        "proxy": proxy.url,
        "fingerprint": json.loads(account.fingerprint),
    })
    add_event(db, f"Аккаунт #{account.id}: слот {slot.id} занят, создаю профиль", code="slot_reserved", account_id=account.id)

    return {"ok": True, "slot": slot.id, "free": slot_service.free_count(db)}


@app.post("/api/accounts/{account_id}/finish")
def finish_account(account_id: int, db: Session = Depends(get_db), _: None = Depends(require_admin)) -> dict[str, Any]:
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")

    had_session = bool(account.session_blob)
    slot_service.release_by_account(db, account)
    account.state = AccountState.DONE
    if not had_session:
        account.error = "Окно закрыто до сохранения сессии"
    db.commit()

    agent_hub.enqueue(db, "close_profile", {
        "account_id": account.id,
        "profile_id": account.profile_id,
    })
    add_event(db, f"Аккаунт #{account.id}: окно закрыто, слот свободен", code="slot_released", account_id=account.id)

    return {"ok": True, "free": slot_service.free_count(db), "has_session": had_session}


@app.post("/api/accounts/{account_id}/reset")
def reset_account(account_id: int, db: Session = Depends(get_db), _: None = Depends(require_admin)) -> dict[str, Any]:
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    if account.state in (AccountState.OPENING, AccountState.IN_ACCOUNT):
        raise HTTPException(status_code=409, detail="Сначала закрой окно")

    account.state = AccountState.READY if account.tdata_key else AccountState.PARSED
    account.error = ""
    db.commit()
    return {"ok": True}


@app.post("/api/accounts/{account_id}/dump")
def dump_account_session(account_id: int, db: Session = Depends(get_db), _: None = Depends(require_admin)) -> dict[str, Any]:
    """Заказать снятие сессии из живого окна (агент сделает через CDP)."""
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    if not account.profile_id:
        raise HTTPException(status_code=409, detail="Окно ещё не открыто")

    agent_hub.enqueue(db, "dump_session", {
        "account_id": account.id,
        "profile_id": account.profile_id,
    })
    add_event(db, f"Аккаунт #{account.id}: запрошено снятие сессии", code="dump_requested", account_id=account.id)
    return {"ok": True}


@app.get("/api/accounts/{account_id}/session")
def download_session(account_id: int, db: Session = Depends(get_db), _: None = Depends(require_admin)) -> Response:
    account = db.get(Account, account_id)
    if not account or not account.session_blob:
        raise HTTPException(status_code=404, detail="Сессии нет")

    raw = decrypt_text(account.session_blob)
    if not raw:
        raise HTTPException(status_code=500, detail="Не удалось расшифровать сессию")

    return Response(
        content=raw,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="session_{account.id}.json"'},
    )


# ---------------------------------------------------------------- events


@app.get("/api/events")
def events(after: int = 0, db: Session = Depends(get_db), _: None = Depends(require_admin)) -> dict[str, Any]:
    rows = db.query(Event).filter(Event.id > after).order_by(Event.id).limit(200).all()
    return {"events": [
        {"id": e.id, "level": e.level, "code": e.code, "message": e.message,
         "account_id": e.account_id, "ts": e.created_at.isoformat() if e.created_at else ""}
        for e in rows
    ]}


# ---------------------------------------------------------------- agent bridge


class PollIn(BaseModel):
    agent_id: str = "default"
    alive: list[str] = []


class ResultIn(BaseModel):
    command_id: int
    status: str
    result: dict[str, Any] = {}


@app.post("/api/agent/poll")
def agent_poll(payload: PollIn, db: Session = Depends(get_db), _: None = Depends(require_agent)) -> dict[str, Any]:
    _reconcile_alive(db, payload.alive)
    commands = agent_hub.take(db, payload.agent_id)
    return {
        "commands": [
            {"id": c.id, "kind": c.kind, "payload": json.loads(c.payload or "{}")}
            for c in commands
        ],
        "max_slots": settings.max_slots,
    }


@app.post("/api/agent/result")
def agent_result(payload: ResultIn, db: Session = Depends(get_db), _: None = Depends(require_agent)) -> dict[str, bool]:
    command = agent_hub.complete(db, payload.command_id, payload.status, payload.result)
    if not command:
        raise HTTPException(status_code=404, detail="Команда не найдена")

    data = payload.result or {}
    if command.kind == "open_profile":
        _apply_open_result(db, command, data)
    elif command.kind == "close_profile":
        add_event(db, f"Профиль {data.get('profile_id', '')} закрыт", code="profile_closed")
    elif command.kind == "dump_session":
        _apply_dump_result(db, data)

    return {"ok": True}


def _apply_open_result(db: Session, command, data: dict[str, Any]) -> None:
    try:
        request_payload = json.loads(command.payload or "{}")
    except json.JSONDecodeError:
        request_payload = {}

    account_id = data.get("account_id") or request_payload.get("account_id")
    account = db.get(Account, account_id) if account_id else None
    if not account:
        return

    if data.get("ok"):
        account.profile_id = str(data.get("profile_id", ""))
        account.state = AccountState.IN_ACCOUNT
        account.error = ""
        db.commit()

        if account.slot_no:
            slot_service.mark_busy(db, account.slot_no, account.profile_id)

        session = data.get("session")
        if session:
            account.session_blob = encrypt_text(json.dumps(session, ensure_ascii=False))
            account.session_saved_at = account.updated_at
            db.commit()
            add_event(db, f"Аккаунт #{account.id}: сессия снята и сохранена", code="session_saved", account_id=account.id)

        add_event(db, f"Аккаунт #{account.id}: окно открыто", code="profile_opened", account_id=account.id)
    else:
        slot_service.release_by_account(db, account)
        account.state = AccountState.FAILED
        account.error = str(data.get("error", "неизвестная ошибка"))[:500]
        db.commit()
        add_event(db, f"Аккаунт #{account.id}: ошибка открытия — {account.error}",
                  code="open_failed", level="error", account_id=account.id)


def _apply_dump_result(db: Session, data: dict[str, Any]) -> None:
    account_id = data.get("account_id")
    account = db.get(Account, account_id) if account_id else None
    if not account:
        return

    session = data.get("session")
    if session:
        account.session_blob = encrypt_text(json.dumps(session, ensure_ascii=False))
        account.session_saved_at = account.updated_at
        db.commit()
        add_event(db, f"Аккаунт #{account.id}: сессия снята и сохранена", code="session_saved", account_id=account.id)
    else:
        add_event(db, f"Аккаунт #{account.id}: сессию снять не удалось — {data.get('error', '')}",
                  code="dump_failed", level="error", account_id=account.id)


def _reconcile_alive(db: Session, alive: list[str]) -> None:
    """Агент говорит, какие профили живы. Всё остальное — окно закрыто → слот свободен."""
    alive_set = set(alive)
    now_ts = __import__("time").time()

    for slot in db.query(Slot).filter(Slot.state != SlotState.FREE).all():
        if not slot.profile_id:
            continue  # профиль ещё создаётся
        if slot.profile_id in alive_set:
            continue
        if slot.updated_at and (now_ts - slot.updated_at.timestamp()) < 10:
            continue  # грейс на старт

        account = db.get(Account, slot.account_id) if slot.account_id else None
        slot_service.release(db, slot.id)
        if account:
            account.state = AccountState.DONE
            account.slot_no = 0
            db.commit()
            add_event(db, f"Аккаунт #{account.id}: окно закрыто извне, слот свободен",
                      code="window_lost", account_id=account.id)


# ---------------------------------------------------------------- errors


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
