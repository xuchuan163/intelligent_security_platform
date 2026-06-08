from pathlib import Path

import pytest

from app.domain.weights import (
    ProjectTypeCoefficients,
    get_project_type_coefficients,
    load_project_type_matrix,
)


def test_project_type_matrix_yaml_loads_four_types():
    matrix = load_project_type_matrix()

    assert matrix.version == "1.0.0"
    assert set(matrix.project_types) == {"housing", "municipal", "infrastructure", "mep"}
    assert matrix.project_types["housing"].equipment_machinery == pytest.approx(1.10)
    assert matrix.project_types["infrastructure"].schedule_pressure == pytest.approx(1.10)


def test_unknown_project_type_uses_neutral_coefficients():
    coef = get_project_type_coefficients("unknown-type")

    assert coef == ProjectTypeCoefficients.neutral()


def test_load_project_type_matrix_accepts_custom_path(tmp_path: Path):
    config = tmp_path / "matrix.yaml"
    config.write_text(
        """
version: "9.9.9"
effective_from: "2099-01-01"
default_type: custom
project_types:
  custom:
    coefficients:
      schedule_pressure: 2.0
""".strip(),
        encoding="utf-8",
    )

    matrix = load_project_type_matrix(config)

    assert matrix.version == "9.9.9"
    assert matrix.project_types["custom"].schedule_pressure == 2.0
