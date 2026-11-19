"""Проверяем главный инвариант: третье окно не открывается."""
from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient

from app.main import app


def make_zip(accounts: int = 3) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for index in range(accounts):
            zf.writestr(f"acc_{index}/tdata/key_datas", "x")
            zf.writestr(f"acc_{index}/tdata/D877F783D5D3EF8C/map0", "x")
    return buffer.getvalue()


def login(client: TestClient) -> None:
    response = client.post("/api/login", json={"password": "test-pass"})
    assert response.status_code == 200


def test_third_window_is_blocked() -> None:
    with TestClient(app) as client:
        login(client)

        # агент должен быть онлайн, иначе панель откажет раньше слота
        response = client.post(
            "/api/agent/poll",
            json={"agent_id": "default", "alive": []},
            headers={"X-Agent-Token": "test-agent"},
        )
        assert response.status_code == 200

        upload = client.post(
            "/api/batches",
            files={"file": ("batch.zip", make_zip(3), "application/zip")},
            data={"proxies": "10.0.0.1:8000:user:pass"},
        )
        assert upload.status_code == 200, upload.text
        assert upload.json()["found"] == 3

        accounts = client.get("/api/state").json()["accounts"]
        assert len(accounts) == 3

        opened = []
        for account in accounts:
            response = client.post(
                f"/api/accounts/{account['id']}/open",
                json={"proxy": "10.0.0.2:8000:user:pass"},
            )
            opened.append(response.status_code)

        assert opened[:2] == [200, 200], opened
        assert opened[2] == 409, opened
        assert "слот" in client.get(f"/api/state").json()["slots"].__str__()

        state = client.get("/api/state").json()
        assert state["slots"]["busy"] == 2
        assert state["slots"]["free"] == 0

        # закрыли одно окно — место освободилось
        done = client.post(f"/api/accounts/{accounts[0]['id']}/finish")
        assert done.status_code == 200
        assert client.get("/api/state").json()["slots"]["free"] == 1

        # и теперь третье открывается
        response = client.post(
            f"/api/accounts/{accounts[2]['id']}/open",
            json={"proxy": "10.0.0.2:8000:user:pass"},
        )
        assert response.status_code == 200, response.text


def test_agent_offline_blocks_open() -> None:
    with TestClient(app) as client:
        login(client)
        upload = client.post(
            "/api/batches",
            files={"file": ("batch2.zip", make_zip(1), "application/zip")},
            data={"proxies": "10.0.0.1:8000"},
        )
        assert upload.status_code == 200
        account = client.get("/api/state").json()["accounts"][0]
        response = client.post(f"/api/accounts/{account['id']}/open", json={"proxy": "10.0.0.2:8000"})
        assert response.status_code in (409, 401)


def test_archive_without_tdata_rejected() -> None:
    with TestClient(app) as client:
        login(client)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("photos/cat.jpg", "x")
        response = client.post(
            "/api/batches",
            files={"file": ("empty.zip", buffer.getvalue(), "application/zip")},
            data={"proxies": "10.0.0.1:8000"},
        )
        assert response.status_code == 400
