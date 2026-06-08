from app.core.config import settings
from app.services.rag.embedding import MockEmbeddingProvider, build_embedding_provider


def test_mock_embedding_returns_expected_dimension():
    provider = MockEmbeddingProvider(dimension=16)
    vectors = provider.embed_texts(["高处作业", "临时用电"])

    assert len(vectors) == 2
    assert len(vectors[0]) == 16
    assert vectors[0] != vectors[1]


def test_build_embedding_provider_defaults_to_mock(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "disabled")

    provider = build_embedding_provider()

    assert provider.provider == "mock"
