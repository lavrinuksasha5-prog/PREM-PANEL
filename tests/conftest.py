"""Тестовая среда: изолированная база и данные, без сети."""
from __future__ import annotations

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="twks_test_")
os.environ.setdefault("TWKS_DATA_DIR", _TMP)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP}/test.db")
os.environ.setdefault("TWKS_ADMIN_PASSWORD", "test-pass")
os.environ.setdefault("TWKS_SECRET_KEY", "test-secret")
os.environ.setdefault("TWKS_AGENT_TOKEN", "test-agent")
os.environ.setdefault("TWKS_MAX_SLOTS", "2")
