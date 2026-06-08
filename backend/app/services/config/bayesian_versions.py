"""Read-only Bayesian model version metadata (Phase 5 L3-E.3)."""

from __future__ import annotations

from typing import Any

from app.domain.bayesian.cpt import (
    DEFAULT_CPT_LEARNED_PATH,
    DEFAULT_CPT_PRIOR_PATH,
    cpt_learned_available,
    load_cpt_learned,
    load_cpt_prior,
)


def list_bayesian_config_versions() -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    if DEFAULT_CPT_PRIOR_PATH.is_file():
        prior = load_cpt_prior(DEFAULT_CPT_PRIOR_PATH)
        items.append(
            {
                "config_key": "bayesian_cpt_prior",
                "model_level": prior.get("model_level", "L3"),
                "version": prior.get("model_version"),
                "structure_version": prior.get("structure_version"),
                "source_path": "config/bayesian/cpt_prior.json",
                "factor_count": prior.get("factor_count"),
                "outcome_count": prior.get("outcome_count"),
            }
        )

    if cpt_learned_available():
        learned = load_cpt_learned()
        items.append(
            {
                "config_key": "bayesian_cpt_learned",
                "model_level": learned.get("model_level", "L3"),
                "version": learned.get("model_version"),
                "structure_version": learned.get("structure_version"),
                "prior_version": learned.get("prior_version"),
                "source_path": "config/bayesian/cpt_learned.json",
                "trained_at": learned.get("trained_at"),
                "case_count": learned.get("case_count"),
                "training_alpha": learned.get("training_alpha"),
                "tenant_id": learned.get("tenant_id"),
            }
        )

    return {"items": items}
