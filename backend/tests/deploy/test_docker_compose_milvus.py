from pathlib import Path


COMPOSE_PATH = Path(__file__).resolve().parents[3] / "deploy" / "docker-compose.yml"


def _compose_text() -> str:
    return COMPOSE_PATH.read_text(encoding="utf-8")


def test_compose_includes_milvus_stack():
    text = _compose_text()
    for service in ("etcd:", "minio:", "milvus:"):
        assert service in text


def test_milvus_depends_on_etcd_and_minio_with_health():
    text = _compose_text()
    assert "condition: service_healthy" in text
    assert "ETCD_ENDPOINTS: etcd:2379" in text
    assert "MINIO_ADDRESS: minio:9000" in text


def test_milvus_exposes_grpc_and_health_ports():
    text = _compose_text()
    assert '"29530:19530"' in text
    assert '"19091:9091"' in text


def test_compose_declares_persistence_volumes():
    text = _compose_text()
    for volume in ("mysql_data:", "redis_data:", "etcd_data:", "minio_data:", "milvus_data:"):
        assert volume in text
