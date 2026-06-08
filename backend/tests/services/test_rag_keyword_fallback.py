import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.infrastructure.database.models import AccidentCaseLibrary
from app.infrastructure.database.session import Base
from app.services.rag.keyword_search import keyword_search_accident_cases
from app.services.rag.search import search_accident_cases_with_fallback


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _seed_case(
    db,
    *,
    accident_case_id: str,
    tenant_id: str = "CSCEC",
    accident_type: str = "高处坠落",
    direct_cause: str = "临边防护缺失",
) -> None:
    db.add(
        AccidentCaseLibrary(
            accident_case_id=accident_case_id,
            tenant_id=tenant_id,
            accident_type=accident_type,
            severity="一般事故",
            project_type="housing",
            operation_scene="主体结构临边作业",
            direct_cause=direct_cause,
            indirect_cause="班前交底不到位",
            involved_subjects={"subjects": ["worker"]},
            warning_indicators=[{"metric_code": "HAZARD_OVERDUE_COUNT", "value": 1}],
            rectification_measures="恢复临边防护并复查",
            tags=["高处作业", "临边防护"],
            status="active",
            created_at=dt.datetime(2026, 6, 1, 9, 0, 0),
        )
    )
    db.commit()


def test_keyword_search_matches_accident_type_and_tenant():
    db = _session()
    _seed_case(db, accident_case_id="AC-001", accident_type="触电", direct_cause="配电箱接地失效")
    _seed_case(db, accident_case_id="AC-002", tenant_id="OTHER", accident_type="触电", direct_cause="配电箱接地失效")

    hits = keyword_search_accident_cases(db, tenant_id="CSCEC", query="触电", limit=10)

    assert len(hits) == 1
    assert hits[0]["accident_case_id"] == "AC-001"


def test_keyword_search_matches_tag_text():
    db = _session()
    _seed_case(db, accident_case_id="AC-003")

    hits = keyword_search_accident_cases(db, tenant_id="CSCEC", query="临边防护", limit=10)

    assert len(hits) == 1
    assert hits[0]["accident_case_id"] == "AC-003"


def test_search_with_fallback_uses_mysql_when_milvus_disabled(monkeypatch):
    monkeypatch.setattr(settings, "milvus_enabled", False)
    db = _session()
    _seed_case(db, accident_case_id="AC-004", accident_type="坍塌", direct_cause="基坑边坡开裂")

    result = search_accident_cases_with_fallback(db, tenant_id="CSCEC", query="坍塌", limit=5)

    assert result["mode"] == "mysql_keyword"
    assert result["total"] == 1
    assert result["items"][0]["record_id"] == "AC-004"


class _FakeMilvusClient:
    def ping(self) -> bool:
        return True

    def has_collection(self, name: str) -> bool:
        return False

    def list_collections(self) -> list[str]:
        return []

    def close(self) -> None:
        return None


def test_search_with_fallback_uses_mysql_when_milvus_has_no_collections(monkeypatch):
    monkeypatch.setattr(settings, "milvus_enabled", True)
    monkeypatch.setattr(
        "app.services.rag.retrieve.build_milvus_client_optional",
        lambda: _FakeMilvusClient(),
    )
    db = _session()
    _seed_case(db, accident_case_id="AC-005", accident_type="机械伤害", direct_cause="防护罩缺失")

    result = search_accident_cases_with_fallback(db, tenant_id="CSCEC", query="机械伤害", limit=5)

    assert result["mode"] == "mysql_keyword"
    assert result["total"] == 1
