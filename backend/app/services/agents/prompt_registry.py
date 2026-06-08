from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.infrastructure.database.models import AgentPromptVersion


ROOT_DIR = Path(__file__).resolve().parents[4]
PROMPT_VERSION = "v1.0"
_VERSION_PATTERN = re.compile(r"^v1\.(\d+)$")


@dataclass(frozen=True)
class AgentPromptSpec:
    agent_code: str
    prompt_file: str

    @property
    def path(self) -> Path:
        return ROOT_DIR / "prompts" / "agents" / self.prompt_file


AGENT_PROMPT_SPECS: tuple[AgentPromptSpec, ...] = (
    AgentPromptSpec("safety_supervisor", "safety_supervisor.md"),
    AgentPromptSpec("risk_profile_analyst", "risk_profile_analyst.md"),
    AgentPromptSpec("rule_compliance_checker", "rule_compliance_checker.md"),
    AgentPromptSpec("work_order_coordinator", "work_order_coordinator.md"),
    AgentPromptSpec("nl2sql_analyst", "nl2sql_analyst.md"),
    AgentPromptSpec("hazard_rectification_advisor", "hazard_rectification_advisor.md"),
)


def _prompt_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _next_prompt_version(db: Session, agent_code: str) -> str:
    rows = db.query(AgentPromptVersion).filter(AgentPromptVersion.agent_code == agent_code).all()
    if not rows:
        return PROMPT_VERSION
    max_minor = 0
    for row in rows:
        match = _VERSION_PATTERN.match(row.prompt_version)
        if match:
            max_minor = max(max_minor, int(match.group(1)))
    return f"v1.{max_minor + 1}"


def _deactivate_agent_prompts(db: Session, agent_code: str) -> None:
    rows = db.query(AgentPromptVersion).filter(AgentPromptVersion.agent_code == agent_code).all()
    for row in rows:
        row.is_active = False
        if row.status == "active":
            row.status = "archived"


def sync_agent_prompt_versions(db: Session) -> dict[str, int]:
    synced_count = 0
    for spec in AGENT_PROMPT_SPECS:
        prompt_hash = _prompt_hash(spec.path)
        active = get_active_prompt_version(db, spec.agent_code)
        if active is None:
            row = AgentPromptVersion(
                agent_code=spec.agent_code,
                prompt_version=PROMPT_VERSION,
                prompt_path=str(spec.path),
                prompt_hash=prompt_hash,
                status="active",
                is_active=True,
            )
            db.add(row)
        elif active.prompt_hash == prompt_hash:
            active.prompt_path = str(spec.path)
            active.status = "active"
            active.is_active = True
        else:
            active.is_active = False
            active.status = "archived"
            db.add(
                AgentPromptVersion(
                    agent_code=spec.agent_code,
                    prompt_version=_next_prompt_version(db, spec.agent_code),
                    prompt_path=str(spec.path),
                    prompt_hash=prompt_hash,
                    status="active",
                    is_active=True,
                )
            )
        synced_count += 1
    db.commit()
    return {"synced_count": synced_count}


def list_active_prompt_versions(db: Session) -> list[AgentPromptVersion]:
    return (
        db.query(AgentPromptVersion)
        .filter(
            AgentPromptVersion.status == "active",
            AgentPromptVersion.is_active.is_(True),
        )
        .order_by(AgentPromptVersion.agent_code.asc())
        .all()
    )


def list_prompt_versions(db: Session, agent_code: str | None = None) -> list[AgentPromptVersion]:
    query = db.query(AgentPromptVersion)
    if agent_code:
        query = query.filter(AgentPromptVersion.agent_code == agent_code)
    return query.order_by(
        AgentPromptVersion.agent_code.asc(),
        AgentPromptVersion.updated_at.desc(),
    ).all()


def get_active_prompt_version(db: Session, agent_code: str) -> AgentPromptVersion | None:
    return (
        db.query(AgentPromptVersion)
        .filter(
            AgentPromptVersion.agent_code == agent_code,
            AgentPromptVersion.status == "active",
            AgentPromptVersion.is_active.is_(True),
        )
        .order_by(AgentPromptVersion.updated_at.desc())
        .first()
    )


def get_prompt_version(db: Session, agent_code: str, prompt_version: str) -> AgentPromptVersion | None:
    return (
        db.query(AgentPromptVersion)
        .filter(
            AgentPromptVersion.agent_code == agent_code,
            AgentPromptVersion.prompt_version == prompt_version,
        )
        .first()
    )


def activate_prompt_version(db: Session, *, agent_code: str, prompt_version: str) -> AgentPromptVersion:
    target = get_prompt_version(db, agent_code, prompt_version)
    if target is None:
        raise ValueError(f"Prompt version {agent_code}/{prompt_version} not found")
    _deactivate_agent_prompts(db, agent_code)
    target.is_active = True
    target.status = "active"
    db.commit()
    db.refresh(target)
    return target


def prompt_version_to_dict(row: AgentPromptVersion) -> dict[str, Any]:
    return {
        "agent_code": row.agent_code,
        "prompt_version": row.prompt_version,
        "prompt_path": row.prompt_path,
        "prompt_hash": row.prompt_hash,
        "status": row.status,
        "is_active": row.is_active,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
