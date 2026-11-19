"""Точка входа Railway.

Умеет два варианта:
1. В репозитории есть папка app/ с main.py — запускаем как есть.
2. GitHub «расплющил» папки и все модули лежат в корне — собираем пакет app
   из плоских файлов прямо в контейнере и запускаем.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# что должно попасть в пакет app
APP_MODULES = [
    "config", "models", "db", "security", "fingerprints",
    "archive", "proxies", "slots", "agent_hub", "main",
]
STATIC_FILES = ["index.html", "app.js", "style.css"]


def tree(path: Path) -> str:
    lines: list[str] = []
    for item in sorted(path.iterdir())[:60]:
        lines.append(f"  {item.name}{'/' if item.is_dir() else ''}")
    return "\n".join(lines)


def assemble_from_flat(root: Path) -> Path | None:
    """Собирает пакет app/ из файлов, лежащих в корне."""
    app_dir = root / "app"
    if not (root / "main.py").is_file():
        return None

    app_dir.mkdir(exist_ok=True)
    (app_dir / "__init__.py").write_text("# собран автоматически из плоских файлов\n", encoding="utf-8")

    copied = []
    for name in APP_MODULES:
        source = root / f"{name}.py"
        if source.is_file():
            shutil.copy2(source, app_dir / f"{name}.py")
            copied.append(f"{name}.py")

    static_dir = app_dir / "static"
    static_dir.mkdir(exist_ok=True)
    for name in STATIC_FILES:
        source = root / name
        if source.is_file():
            shutil.copy2(source, static_dir / name)
            copied.append(f"static/{name}")

    print(f"[twks] пакет собран из корня, файлов: {len(copied)}", flush=True)
    print("[twks] " + ", ".join(copied), flush=True)
    return app_dir


def find_app_dir() -> Path:
    direct = ROOT / "app" / "main.py"
    if direct.is_file():
        return ROOT / "app"

    for folder in sorted(ROOT.rglob("app")):
        if folder.is_dir() and (folder / "main.py").is_file():
            return folder

    assembled = assemble_from_flat(ROOT)
    if assembled and (assembled / "main.py").is_file():
        return assembled

    print("[twks] не нашёл ни app/, ни main.py в корне. Что лежит в контейнере:", flush=True)
    print(tree(ROOT), flush=True)
    raise SystemExit(1)


APP_DIR = find_app_dir()
sys.path.insert(0, str(APP_DIR.parent))
print(f"[twks] проект найден: {APP_DIR}", flush=True)

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        log_level="info",
    )
