from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints import metrics
from app.infrastructure.database.models import MetricCatalog
from app.infrastructure.database.session import Base
from app.main import app


def _override_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    db.add(
        MetricCatalog(
            metric_code="PROJECT_RISK_SCORE",
            metric_name="项目风险分",
            business_definition="项目风险画像总分",
            calculation_formula="base_score * dynamic_factor + rule_bonus",
            dimensions=["tenant_id", "project_id"],
            source_tables=["project_risk_profile"],
            source_fields=["total_risk_score"],
            filters={"status": "active"},
            aliases=["项目风险", "风险分"],
            status="enabled",
        )
    )
    db.commit()
    db.close()

    def dependency():
        scoped = SessionLocal()
        try:
            yield scoped
        finally:
            scoped.close()

    return dependency


def test_metrics_validate_lineage_and_aliases_routes_return_success():
    client = TestClient(app)
    app.dependency_overrides[metrics.get_db] = _override_db()

    try:
        validate_response = client.post(
            "/api/v1/metrics/validate",
            json={"metric_codes": ["PROJECT_RISK_SCORE"]},
        )
        lineage_response = client.get("/api/v1/metrics/lineage/PROJECT_RISK_SCORE")
        aliases_response = client.get("/api/v1/metrics/aliases?keyword=风险")

        assert validate_response.status_code == 200
        assert validate_response.json()["data"]["valid"] is True
        assert lineage_response.status_code == 200
        assert lineage_response.json()["data"]["source_tables"] == ["project_risk_profile"]
        assert aliases_response.status_code == 200
        assert aliases_response.json()["data"]["items"][0]["aliases"] == ["项目风险", "风险分"]
    finally:
        app.dependency_overrides.clear()
