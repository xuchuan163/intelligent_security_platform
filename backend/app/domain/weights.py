from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ProjectTypeCoefficients:
    high_risk_operation: float = 1.0
    equipment_machinery: float = 1.0
    environment_monitoring: float = 1.0
    schedule_pressure: float = 1.0
    subcontractor_transmission: float = 1.0

    @classmethod
    def neutral(cls) -> ProjectTypeCoefficients:
        return cls()

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> ProjectTypeCoefficients:
        return cls(
            high_risk_operation=float(payload.get("high_risk_operation", 1.0)),
            equipment_machinery=float(payload.get("equipment_machinery", 1.0)),
            environment_monitoring=float(payload.get("environment_monitoring", 1.0)),
            schedule_pressure=float(payload.get("schedule_pressure", 1.0)),
            subcontractor_transmission=float(payload.get("subcontractor_transmission", 1.0)),
        )


@dataclass(frozen=True)
class ProjectTypeMatrix:
    version: str
    effective_from: str
    default_type: str
    project_types: dict[str, ProjectTypeCoefficients]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_project_type_matrix(
    config_path: Path | None = None,
) -> ProjectTypeMatrix:
    path = config_path or _repo_root() / "config" / "weights" / "project_type_matrix.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    project_types: dict[str, ProjectTypeCoefficients] = {}

    for type_code, entry in (payload.get("project_types") or {}).items():
        coefficients = (entry or {}).get("coefficients") or {}
        project_types[type_code] = ProjectTypeCoefficients.from_mapping(coefficients)

    return ProjectTypeMatrix(
        version=str(payload.get("version", "0.0.0")),
        effective_from=str(payload.get("effective_from", "")),
        default_type=str(payload.get("default_type", "default")),
        project_types=project_types,
    )


@lru_cache(maxsize=1)
def default_project_type_matrix() -> ProjectTypeMatrix:
    return load_project_type_matrix()


def get_project_type_coefficients(
    project_type: str | None,
    *,
    matrix: ProjectTypeMatrix | None = None,
) -> ProjectTypeCoefficients:
    if not project_type:
        return ProjectTypeCoefficients.neutral()

    resolved = matrix or default_project_type_matrix()
    return resolved.project_types.get(project_type, ProjectTypeCoefficients.neutral())


def weighted_project_base_score(
    project_type: str | None,
    *,
    hazard_overdue_count: int,
    equipment_overdue_count: int,
    schedule_pressure_index: float,
    matrix: ProjectTypeMatrix | None = None,
) -> tuple[float, list[str]]:
    """Apply project-type coefficients to the simplified MVP project base formula."""

    resolved = matrix or default_project_type_matrix()
    coef = get_project_type_coefficients(project_type, matrix=resolved)
    hazard_component = hazard_overdue_count * 8 * coef.high_risk_operation
    equipment_component = equipment_overdue_count * 10 * coef.equipment_machinery
    schedule_component = schedule_pressure_index * coef.schedule_pressure
    base_score = min(60.0, hazard_component + equipment_component + schedule_component)

    evidence: list[str] = []
    if project_type:
        evidence.append(f"weight:project_type:{project_type}")
        evidence.append(f"weight:version:{resolved.version}")

    return round(base_score, 2), evidence
