from __future__ import annotations

from typing import Any

from app.domain.dynamic_factors import load_dynamic_factor_config
from app.domain.weights import load_project_type_matrix


def list_weight_config_versions() -> dict[str, Any]:
    project_matrix = load_project_type_matrix()
    dynamic_factors = load_dynamic_factor_config()

    return {
        "items": [
            {
                "config_key": "project_type_matrix",
                "version": project_matrix.version,
                "effective_from": project_matrix.effective_from,
                "source_path": "config/weights/project_type_matrix.yaml",
                "default_type": project_matrix.default_type,
                "project_type_count": len(project_matrix.project_types),
                "project_types": sorted(project_matrix.project_types),
            },
            {
                "config_key": "dynamic_factors",
                "version": dynamic_factors.version,
                "effective_from": dynamic_factors.effective_from,
                "source_path": "config/weights/dynamic_factors.yaml",
                "base_factor": dynamic_factors.base_factor,
                "max_factor": dynamic_factors.max_factor,
                "factor_count": len(dynamic_factors.factors),
                "factor_codes": [factor.factor_code for factor in dynamic_factors.factors],
                "exclusive_groups": sorted(dynamic_factors.exclusive_groups),
            },
        ]
    }
