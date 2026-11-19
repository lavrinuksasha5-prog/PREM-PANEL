"""Разбор ZIP-архива: ищем tdata на любой глубине.

В архиве может быть:
  tdata/key_datas
  acc_01/tdata/key_datas
  acc_01/Telegram/tdata/key_datas
  мусор, скриншоты, txt с паролями
Задача — вытащить все папки tdata и не сломаться на мусоре.
"""
from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# файл, который 100% есть в живой tdata
MARKER = "key_datas"


@dataclass
class TdataEntry:
    key: str                     # путь к папке tdata внутри архива
    root: str = ""               # родительская папка (может содержать телефон/пароль)
    notes: list[str] = field(default_factory=list)


def _is_tdata_dir(name: str) -> bool:
    return Path(name).name.lower() == "tdata"


def scan_zip(zip_path: str | Path) -> list[TdataEntry]:
    """Возвращает список найденных tdata-папок."""
    found: dict[str, TdataEntry] = {}

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()

        # 1) ищем файлы-маркеры и берём их родительскую папку
        for name in names:
            parts = Path(name).parts
            if not parts or parts[-1] != MARKER:
                continue
            parent = str(Path(name).parent).replace("\\", "/")
            if parent in (".", ""):
                continue
            if not _is_tdata_dir(parent):
                continue
            found.setdefault(parent, TdataEntry(key=parent, root=str(Path(parent).parent)))

        # 2) если маркер не нашли (архив упакован криво) — берём любую папку tdata
        if not found:
            for name in names:
                parts = Path(name).parts
                for i, part in enumerate(parts):
                    if part.lower() == "tdata":
                        parent = "/".join(parts[: i + 1])
                        found.setdefault(parent, TdataEntry(key=parent))

        # 3) подтягиваем txt-подсказки (2FA, пароли) из той же папки-родителя
        for entry in found.values():
            prefix = f"{entry.root}/" if entry.root and entry.root != "." else ""
            for name in names:
                if not name.lower().endswith((".txt", ".json")):
                    continue
                if prefix and not name.startswith(prefix):
                    continue
                if name.count("/") - prefix.count("/") > 1:
                    continue
                entry.notes.append(name)

    return sorted(found.values(), key=lambda e: e.key)


def extract_tdata(zip_path: str | Path, key: str, dest_dir: str | Path) -> Path:
    """Распаковывает одну tdata-папку в dest_dir и возвращает путь к tdata."""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    prefix = key.rstrip("/") + "/"

    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.startswith(prefix):
                continue
            relative = name[len(prefix):]
            if not relative:
                continue
            target = dest / relative
            if name.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name) as src, open(target, "wb") as out:
                out.write(src.read())

    return dest
