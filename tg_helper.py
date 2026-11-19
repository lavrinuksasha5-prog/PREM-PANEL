import asyncio
import io
import os
import re
import zipfile
from pathlib import Path

import httpx

PANEL = os.getenv("TWKS_PANEL_URL", "http://127.0.0.1:8000").rstrip("/")
TOKEN = os.getenv("TWKS_AGENT_TOKEN", "agent-secret")
WORK = Path(os.getenv("TWKS_TDATA_DIR", str(Path(__file__).resolve().parent / "tdata")))
CODE_RE = re.compile(r"(\d{5,6})")


def download_tdata(account_id):
    folder = WORK / str(account_id)
    tdata = folder / "tdata"
    if (tdata / "key_datas").exists():
        return tdata
    url = PANEL + "/api/agent/tdata/" + str(account_id)
    r = httpx.get(url, headers={"X-Agent-Token": TOKEN}, timeout=120)
    r.raise_for_status()
    folder.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        zf.extractall(tdata)
    return tdata


async def build_client(account_id):
    from opentele.api import API, UseCurrentSession
    from opentele.td import TDesktop
    tdata = download_tdata(account_id)
    desktop = TDesktop(str(tdata))
    session_file = WORK / (str(account_id) + ".session")
    client = await desktop.ToTelethon(session=str(session_file), api=API.TelegramDesktop, flag=UseCurrentSession)
    await client.connect()
    return client


async def phone_of(account_id):
    client = await build_client(account_id)
    try:
        me = await client.get_me()
        return (me.phone or "") if me else ""
    finally:
        await client.disconnect()


async def wait_code(account_id, timeout=180):
    client = await build_client(account_id)
    try:
        me = await client.get_me()
        print("аккаунт:", me.first_name if me else "?", "| +" + (me.phone or ""), flush=True)
        last_id = 0
        try:
            history = await client.get_messages(777000, limit=1)
            if history:
                last_id = history[0].id
        except Exception:
            pass
        waited = 0
        seen = False
        while waited < timeout:
            await asyncio.sleep(1)
            waited += 1
            try:
                msgs = await client.get_messages(777000, limit=5)
            except Exception:
                continue
            for msg in msgs:
                text = msg.message or ""
                if text and not seen:
                    print("777000:", text[:90].replace(chr(10), " "), flush=True)
                    seen = True
                m = CODE_RE.search(text)
                if m:
                    return m.group(1)
        return ""
    finally:
        await client.disconnect()


if __name__ == "__main__":
    import sys
    account = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    print("скачиваю tdata аккаунта", account, flush=True)
    print("телефон: +" + asyncio.run(phone_of(account)), flush=True)



