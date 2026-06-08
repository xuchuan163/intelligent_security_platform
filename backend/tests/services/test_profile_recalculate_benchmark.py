"""Profile recalculate benchmark tests (Phase 4-C.6)."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.session import Base
from app.services.scale.pool_tuning import build_pool_tuning_recommendations, render_pool_tuning_markdown
from app.services.scale.profile_recalculate_benchmark import (
    RecalculateBenchmarkConfig,
    run_profile_recalculate_benchmark,
    run_single_scenario,
)
from app.services.scale.seed_scale_data import ScaleSeedConfig, seed_scale_data


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_run_single_scenario_service_mode_counts_entities(monkeypatch):
    db = _session()
    seed_scale_data(
        db,
        ScaleSeedConfig(
            tenant_id="TENANT-RECALC-BENCH",
            project_count=3,
            subcontractors_per_project=1,
            workers_per_project=2,
            with_profiles=False,
        ),
    )

    monkeypatch.setattr(
        "app.services.scale.profile_recalculate_benchmark.SessionLocal",
        lambda: db,
    )

    result = run_single_scenario(
        RecalculateBenchmarkConfig(tenant_id="TENANT-RECALC-BENCH", projects=3),
        scenario_name="full_batch",
        profile_types=["project", "worker", "subcontractor"],
        db=db,
        resolved_mode="service",
    )

    assert result["status_code"] == 200
    assert result["counts"]["recalculated_projects"] == 3
    assert result["counts"]["recalculated_workers"] == 6
    assert result["counts"]["recalculated_subcontractors"] == 3
    assert result["sla_passed"] is True


def test_build_pool_tuning_recommendations_for_large_scale():
    benchmark = {
        "meta": {"projects": 2000},
        "summary": {"full_batch_elapsed_seconds": 45.2},
    }
    tuning = build_pool_tuning_recommendations(benchmark)

    assert tuning["current"]["pool_size"] == 10
    assert any(item["area"] == "连接池" for item in tuning["recommendations"])
    assert any("45.2s" in item["action"] for item in tuning["recommendations"])
    markdown = render_pool_tuning_markdown(tuning)
    assert "DB_POOL_SIZE" in markdown


def test_run_profile_recalculate_benchmark_generates_scenarios(monkeypatch):
    db = _session()
    seed_scale_data(
        db,
        ScaleSeedConfig(
            tenant_id="TENANT-RECALC-API",
            project_count=2,
            subcontractors_per_project=1,
            workers_per_project=1,
            with_profiles=False,
        ),
    )

    monkeypatch.setattr(
        "app.services.scale.profile_recalculate_benchmark.resolve_benchmark_mode",
        lambda config: ("service", ["service mode for unit test"]),
    )
    monkeypatch.setattr(
        "app.services.scale.profile_recalculate_benchmark.SessionLocal",
        lambda: db,
    )

    report = run_profile_recalculate_benchmark(
        RecalculateBenchmarkConfig(
            tenant_id="TENANT-RECALC-API",
            projects=2,
            skip_seed=True,
        )
    )

    assert len(report["scenarios"]) == 4
    assert report["summary"]["sla_passed"] is True
    full_batch = next(item for item in report["scenarios"] if item["name"] == "full_batch")
    assert full_batch["counts"]["recalculated_projects"] == 2
