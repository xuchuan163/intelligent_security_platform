from pathlib import Path

from app.services.rag.chunking import chunk_markdown_file, load_knowledge_chunks, parse_markdown_tags

REPO_ROOT = Path(__file__).resolve().parents[3]
KNOWLEDGE_DIR = REPO_ROOT / "config" / "knowledge"


def test_parse_markdown_tags():
    text = "# Title\n\n标签: 高处作业, 临边防护\n\n## Section\nbody"
    assert parse_markdown_tags(text) == ["高处作业", "临边防护"]


def test_load_knowledge_chunks_has_at_least_ten_sections():
    chunks = load_knowledge_chunks(KNOWLEDGE_DIR, tenant_id="CSCEC")

    assert len(chunks) >= 10
    assert all(chunk.tenant_id == "CSCEC" for chunk in chunks)
    assert all(chunk.chunk_id.startswith("SK-CSCEC-") for chunk in chunks)


def test_chunk_markdown_file_generates_sections_from_seed_corpus():
    path = KNOWLEDGE_DIR / "高处作业安全.md"
    chunks = chunk_markdown_file(path, tenant_id="CSCEC")

    assert len(chunks) >= 3
    assert chunks[0].title
    assert chunks[0].content
