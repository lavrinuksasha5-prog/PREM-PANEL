"""Канал «панель → агент» на ПК.

Агент сам стучится наружу (poll), поэтому проброс портов и белый IP не нужны.
Панель только кладёт команды в очередь и забирает результат.
"""
from __future__ import annotations

import json
import time
from typing import Any

from sqlalchemy.orm import Session

from .config import settings
from .models import AgentCommand

# agent_id -> timestamp последнего poll (в памяти процесса панели)
_agents: dict[str, float] = {}


def touch_agent(agent_id: str) -> None:
    _agents[agent_id] = time.time()


def agent_online(agent_id: str = "default") -> bool:
    last = _agents.get(agent_id)
    return bool(last and (time.time() - last) <= settings.agent_online_ttl)


def agents_status() -> dict[str, Any]:
    return {
        "default": {
            "online": agent_online("default"),
            "last_seen": _agents.get("default", 0),
        }
    }


def enqueue(db: Session, kind: str, payload: dict[str, Any], agent_id: str = "default") -> AgentCommand:
    command = AgentCommand(
        agent_id=agent_id,
        kind=kind,
        payload=json.dumps(payload, ensure_ascii=False),
        status="pending",
    )
    db.add(command)
    db.commit()
    db.refresh(command)
    return command


def take(db: Session, agent_id: str = "default", limit: int = 5) -> list[AgentCommand]:
    touch_agent(agent_id)
    commands = (
        db.query(AgentCommand)
        .filter(AgentCommand.agent_id == agent_id, AgentCommand.status == "pending")
        .order_by(AgentCommand.id)
        .limit(limit)
        .all()
    )
    for command in commands:
        command.status = "sent"
    db.commit()
    return commands


def complete(db: Session, command_id: int, status: str, result: dict[str, Any]) -> AgentCommand | None:
    command = db.get(AgentCommand, command_id)
    if not command:
        return None
    command.status = status
    command.result = json.dumps(result, ensure_ascii=False)[:8000]
    db.commit()
    db.refresh(command)
    return command
