from pathlib import Path

import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database.models import MetricCatalog
from app.infrastructure.database.session import Base
from app.services.metrics.service import get_metric_lineage, list_metric_aliases, validate_metric_contract
from scripts.seed_demo_data import seed_metrics


ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = ROOT / "config" / "metrics" / "catalog.yaml"


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_metric_catalog_yaml_has_at_least_100_enabled_metrics_with_aliases():
    payload = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))
    metrics = payload["metrics"]

    enabled = [metric for metric in metrics if metric["status"] == "enabled"]
    metric_codes = [metric["metric_code"] for metric in metrics]

    assert len(enabled) >= 100
    assert len(metric_codes) == len(set(metric_codes))
    assert {"PROJECT_RISK_SCORE", "WORKER_HIGH_RISK_RATIO", "SUB_OVERDUE_RECT_RATE"} <= set(metric_codes)
    assert any("项目风险分" in (metric.get("aliases") or []) for metric in metrics)


def test_seed_metrics_upserts_yaml_catalog():
    db = _session()

    seed_metrics(db)
    seed_metrics(db)

    rows = db.query(MetricCatalog).all()
    assert len(rows) >= 100
    row = db.query(MetricCatalog).filter(MetricCatalog.metric_code == "PROJECT_RISK_SCORE").one()
    assert "项目风险分" in row.aliases


def test_validate_metric_contract_reports_valid_metric_and_missing_metadata():
    db = _session()
    db.add_all(
        [
            MetricCatalog(
                metric_code="VALID_METRIC",
                metric_name="有效指标",
                business_definition="用于验证完整指标元数据",
                calculation_formula="count(id)",
                dimensions=["tenant_id"],
                source_tables=["project"],
                source_fields=["project_id"],
                filters={},
                aliases=["完整指标"],
                status="enabled",
            ),
            MetricCatalog(
                metric_code="BROKEN_METRIC",
                metric_name="缺失指标",
                business_definition="用于验证错误输出",
                status="enabled",
            ),
        ]
    )
    db.commit()

    valid = validate_metric_contract(db, ["VALID_METRIC"])
    broken = validate_metric_contract(db, ["BROKEN_METRIC", "MISSING_METRIC"])

    assert valid["valid"] is True
    assert valid["items"][0]["metric_code"] == "VALID_METRIC"
    assert valid["items"][0]["errors"] == []
    assert broken["valid"] is False
    assert "source_tables is required" in broken["items"][0]["errors"]
    assert broken["items"][1]["errors"] == ["metric not found"]


def test_get_metric_lineage_returns_sources_dimensions_filters_and_aliases():
    db = _session()
    db.add(
        MetricCatalog(
            metric_code="PROJECT_RISK_SCORE",
            metric_name="项目风险分",
            business_definition="项目风险画像总分",
            calculation_formula="base_score * dynamic_factor + rule_bonus",
            dimensions=["tenant_id", "project_id"],
            source_tables=["project_risk_profile"],
            source_fields=["total_risk_score", "risk_level"],
            filters={"status": "active"},
            aliases=["项目风险", "风险分"],
            status="enabled",
        )
    )
    db.commit()

    data = get_metric_lineage(db, "PROJECT_RISK_SCORE")

    assert data == {
        "metric_code": "PROJECT_RISK_SCORE",
        "metric_name": "项目风险分",
        "calculation_formula": "base_score * dynamic_factor + rule_bonus",
        "dimensions": ["tenant_id", "project_id"],
        "source_tables": ["project_risk_profile"],
        "source_fields": ["total_risk_score", "risk_level"],
        "filters": {"status": "active"},
        "aliases": ["项目风险", "风险分"],
    }


def test_list_metric_aliases_filters_enabled_metrics_and_keyword_matches_alias():
    db = _session()
    db.add_all(
        [
            MetricCatalog(
                metric_code="PROJECT_RISK_SCORE",
                metric_name="项目风险分",
                business_definition="项目风险画像总分",
                aliases=["项目风险", "风险分"],
                status="enabled",
            ),
            MetricCatalog(
                metric_code="DISABLED_METRIC",
                metric_name="停用指标",
                business_definition="停用",
                aliases=["停用"],
                status="disabled",
            ),
        ]
    )
    db.commit()

    data = list_metric_aliases(db, keyword="风险")

    assert data["total"] == 1
    assert data["items"] == [
        {
            "metric_code": "PROJECT_RISK_SCORE",
            "metric_name": "项目风险分",
            "aliases": ["项目风险", "风险分"],
        }
    ]
