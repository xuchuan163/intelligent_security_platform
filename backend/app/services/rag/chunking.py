from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KnowledgeChunkDraft:
    chunk_id: str
    tenant_id: str
    source_doc: str
    title: str
    content: str
    tags: list[str]


_TAG_PATTERN = re.compile(r"^标签:\s*(.+)$", re.MULTILINE)


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", value.strip().lower())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned or "section"


def parse_markdown_tags(text: str) -> list[str]:
    match = _TAG_PATTERN.search(text)
    if not match:
        return []
    return [tag.strip() for tag in match.group(1).split(",") if tag.strip()]


def chunk_markdown_file(
    path: Path,
    *,
    tenant_id: str,
    doc_stem: str | None = None,
) -> list[KnowledgeChunkDraft]:
    text = path.read_text(encoding="utf-8")
    source_doc = doc_stem or path.stem
    tags = parse_markdown_tags(text)

    chunks: list[KnowledgeChunkDraft] = []
    current_title = source_doc
    current_lines: list[str] = []

    def flush(section_index: int) -> None:
        content = "\n".join(line.strip() for line in current_lines if line.strip())
        if not content:
            return
        chunk_id = f"SK-{tenant_id}-{_slugify(source_doc)}-{section_index:03d}"
        chunks.append(
            KnowledgeChunkDraft(
                chunk_id=chunk_id,
                tenant_id=tenant_id,
                source_doc=source_doc,
                title=current_title,
                content=content,
                tags=tags,
            )
        )

    section_index = 0
    for line in text.splitlines():
        if line.startswith("## "):
            if current_lines:
                flush(section_index)
                section_index += 1
            current_title = line[3:].strip()
            current_lines = []
            continue
        if line.startswith("# "):
            continue
        if line.startswith("标签:"):
            continue
        current_lines.append(line)

    if current_lines:
        flush(section_index)

    return chunks


def load_knowledge_chunks(knowledge_dir: Path, *, tenant_id: str) -> list[KnowledgeChunkDraft]:
    chunks: list[KnowledgeChunkDraft] = []
    for path in sorted(knowledge_dir.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        chunks.extend(chunk_markdown_file(path, tenant_id=tenant_id))
    return chunks
