"""Конфиг панели. Всё через ENV, ничего не хардкодим."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# читаем .env рядом с проектом, переменные окружения имеют приоритет
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    def __init__(self) -> None:
        self.admin_password: str = os.getenv("TWKS_ADMIN_PASSWORD", "change-me")
        self.secret_key: str = os.getenv("TWKS_SECRET_KEY", "dev-secret-change-me")

        self.data_dir: Path = Path(os.getenv("TWKS_DATA_DIR", str(Path.cwd() / "data")))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "archives").mkdir(exist_ok=True)

        # Railway подставляет DATABASE_URL сам; локально — sqlite
        default_db = f"sqlite:///{(self.data_dir / 'twks.db').as_posix()}"
        self.database_url: str = os.getenv("DATABASE_URL", default_db)
        # Railway иногда отдаёт postgres:// — приводим к рабочему драйверу
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace("postgresql://", "postgresql+psycopg2://", 1)

        self.max_slots: int = int(os.getenv("TWKS_MAX_SLOTS", "2"))

        # Окто
        self.octo_mock: bool = _bool(os.getenv("TWKS_OCTO_MOCK"), True)
        self.octo_base_url: str = os.getenv("TWKS_OCTO_BASE_URL", "http://127.0.0.1:58888")
        self.octo_token: str = os.getenv("TWKS_OCTO_TOKEN", "")

        # агент
        self.agent_token: str = os.getenv("TWKS_AGENT_TOKEN", "agent-secret")
        self.agent_online_ttl: int = int(os.getenv("TWKS_AGENT_ONLINE_TTL", "15"))

        # сессия админа
        self.cookie_name: str = "twks_session"
        self.session_ttl: int = 60 * 60 * 24 * 7


settings = Settings()
