"""Точка входа Railway."""
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODS = "config models db security fingerprints archive proxies slots agent_hub main".split()
STATIC = "index.html app.js cards.js actions.js style.css".split()


def find_app():
    if (ROOT / "app" / "main.py").is_file():
        return ROOT / "app"
    for folder in sorted(ROOT.rglob("app")):
        if (folder / "main.py").is_file():
            return folder
    if (ROOT / "main.py").is_file():
        target = ROOT / "app"
        target.mkdir(exist_ok=True)
        (target / "__init__.py").write_text("")
        for mod in MODS:
            src = ROOT / (mod + ".py")
            if src.is_file():
                shutil.copy2(src, target / (mod + ".py"))
        static = target / "static"
        static.mkdir(exist_ok=True)
        for name in STATIC:
            src = ROOT / name
            if src.is_file():
                shutil.copy2(src, static / name)
        return target
    print("[twks] нет app/main.py")
    raise SystemExit(1)


APP = find_app()
sys.path.insert(0, str(APP.parent))
print("[twks] проект:", APP, flush=True)

import uvicorn
from fastapi import Body, Depends, Header, HTTPException
from fastapi.responses import FileResponse

from app.config import settings
from app.db import SessionLocal
from app.main import app as fastapi_app
from app.models import Account
from app.security import require_admin


@fastapi_app.get("/api/agent/tdata/{account_id}")
def agent_tdata(account_id: int, x_agent_token: str = Header(default="")):
    if x_agent_token != settings.agent_token:
        raise HTTPException(status_code=401, detail="bad token")
    db = SessionLocal()
    try:
        account = db.get(Account, account_id)
        if not account:
            raise HTTPException(status_code=404, detail="account")
        key = account.tdata_key
    finally:
        db.close()
    if not key:
        raise HTTPException(status_code=404, detail="empty key")
    prefix = key.rstrip("/") + "/"
    archives = Path(settings.data_dir) / "archives"
    for archive in sorted(archives.glob("*.zip"), reverse=True):
        try:
            with zipfile.ZipFile(archive) as src:
                names = src.namelist()
                if not any(n.startswith(prefix) for n in names):
                    continue
                target = Path(tempfile.mkdtemp()) / ("tdata_%d.zip" % account_id)
                with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as out:
                    for name in names:
                        if name.endswith("/"):
                            continue
                        if name.startswith(prefix):
                            out.writestr(name[len(prefix):], src.read(name))
                        elif name.lower().endswith((".txt", ".json")):
                            out.writestr("notes/" + name.replace("/", "_"), src.read(name))
                return FileResponse(target, media_type="application/zip",
                                    filename="tdata_%d.zip" % account_id)
        except zipfile.BadZipFile:
            continue
    raise HTTPException(status_code=404, detail="tdata not found")


@fastapi_app.post("/api/accounts/{account_id}/remove")
def remove_account(account_id: int, _: None = Depends(require_admin)):
    db = SessionLocal()
    try:
        account = db.get(Account, account_id)
        if not account:
            raise HTTPException(status_code=404, detail="account")
        if account.state in ("opening", "in_account"):
            raise HTTPException(status_code=409, detail="сначала закройте окно")
        db.delete(account)
        db.commit()
        return {"ok": True}
    finally:
        db.close()


@fastapi_app.post("/api/accounts/{account_id}/setproxy")
def set_proxy(account_id: int, payload: dict = Body(default={}),
              _: None = Depends(require_admin)):
    proxy = str(payload.get("proxy", "")).strip()
    db = SessionLocal()
    try:
        account = db.get(Account, account_id)
        if not account:
            raise HTTPException(status_code=404, detail="account")
        account.proxy_web = proxy
        account.proxy_import = proxy or account.proxy_import
        account.error = ""
        db.commit()
        return {"ok": True}
    finally:
        db.close()


@fastapi_app.post("/api/accounts/{account_id}/premium")
def set_premium(account_id: int, payload: dict = Body(default={}),
                _: None = Depends(require_admin)):
    db = SessionLocal()
    try:
        account = db.get(Account, account_id)
        if not account:
            raise HTTPException(status_code=404, detail="account")
        account.premium = bool(payload.get("premium", True))
        db.commit()
        return {"ok": True}
    finally:
        db.close()


@fastapi_app.post("/api/accounts/clear_done")
def clear_done(_: None = Depends(require_admin)):
    db = SessionLocal()
    try:
        rows = db.query(Account).filter(Account.state == "done").all()
        for row in rows:
            db.delete(row)
        db.commit()
        return {"ok": True, "removed": len(rows)}
    finally:
        db.close()


if __name__ == "__main__":
    uvicorn.run(fastapi_app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
