from app.core.security import DataScope, MockUser, ScopeType
from app.services.agents.dag_executor import _execute_read_only_tool, _read_graph_neighbors
from app.services.agents.tool_registry import ToolExecutionContext, evaluate_tool_access
from app.services.graph.neighbors import get_graph_neighbors


class FakeNeo4jClient:
    def __init__(self, rows: list[dict] | None = None, anchor: dict | None = None) -> None:
        self.rows = rows or []
        self.anchor = anchor or {
            "labels": ["Project"],
            "properties": {
                "project_id": "P001",
                "tenant_id": "CSCEC",
                "org_path": "CSCEC/P001",
                "project_name": "演示项目",
            },
        }
        self.closed = False

    def run_query(self, query: str, parameters: dict | None = None) -> list[dict]:
        if "RETURN labels(n)" in query:
            return [self.anchor]
        return self.rows

    def close(self) -> None:
        self.closed = True

    def ping(self) -> bool:
        return True


def _user() -> MockUser:
    return MockUser(
        user_id="U-GRAPH",
        user_name="Graph User",
        tenant_id="CSCEC",
        org_path="CSCEC",
        role="company_analyst",
        data_scope=DataScope.TENANT,
        scope_type=ScopeType.COMPANY,
    )


def test_graph_read_neighbors_tool_is_read_only():
    decision = evaluate_tool_access(
        "graph.read_neighbors",
        ToolExecutionContext(
            execution_mode="controlled_execute",
            current_user=_user(),
            project_id="P001",
        ),
    )
    assert decision.status == "ready"
    assert decision.will_execute is True


def test_get_graph_neighbors_filters_out_of_scope_nodes():
    client = FakeNeo4jClient(
        rows=[
            {
                "relationship": "HAS_HAZARD",
                "labels": ["Hazard"],
                "properties": {
                    "hazard_id": "H001",
                    "tenant_id": "OTHER",
                    "org_path": "OTHER/H001",
                },
            },
            {
                "relationship": "HAS_HAZARD",
                "labels": ["Hazard"],
                "properties": {
                    "hazard_id": "H002",
                    "tenant_id": "CSCEC",
                    "org_path": "CSCEC/P001",
                    "hazard_type": "scaffold",
                },
            },
        ]
    )
    report = get_graph_neighbors(
        client,
        node_type="project",
        node_id="P001",
        depth=1,
        current_user=_user(),
    )
    assert report is not None
    assert report["neighbor_count"] == 1
    assert report["neighbors"][0]["properties"]["hazard_id"] == "H002"


def test_read_graph_neighbors_tool_degrades_when_neo4j_unavailable(monkeypatch):
    monkeypatch.setattr(
        "app.services.agents.dag_executor.build_neo4j_client_optional",
        lambda: None,
    )
    result = _read_graph_neighbors(
        current_user=_user(),
        context={"node_type": "project", "node_id": "P001"},
    )
    assert result["row_count"] == 0
    assert result["note"] == "neo4j_unavailable"


def test_execute_read_only_tool_graph_branch(monkeypatch):
    fake = FakeNeo4jClient(
        rows=[
            {
                "relationship": "WORKS_ON",
                "labels": ["Worker"],
                "properties": {
                    "worker_id": "W001",
                    "tenant_id": "CSCEC",
                    "org_path": "CSCEC/P001",
                },
            }
        ]
    )
    monkeypatch.setattr(
        "app.services.agents.dag_executor.build_neo4j_client_optional",
        lambda: fake,
    )
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.infrastructure.database.session import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    result = _execute_read_only_tool(
        db,
        tool_name="graph.read_neighbors",
        current_user=_user(),
        project_id="P001",
        context={"node_type": "project", "node_id": "P001"},
    )
    assert result["row_count"] == 1
    assert fake.closed is True
