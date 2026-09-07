"""Parent–child chunks carry FR-042 metadata (Step 3.2)."""

from __future__ import annotations

import pytest

from aegis.application.rag.allowlist import ALLOWED_RELATIVE_PATHS, repository_root
from aegis.application.rag.chunking import (
    chunk_allowlisted_corpus,
    chunk_document,
    parent_chunks,
    retrieval_chunks,
)

REPO = repository_root()
RUNBOOK = "docs/knowledge/runbooks/payment-latency-spike.md"
ADR_002 = "docs/adr/ADR-002-postgresql.md"


def test_runbook_frontmatter_is_copied_onto_every_chunk() -> None:
    chunks = chunk_document(RUNBOOK, repo_root=REPO)
    assert chunks
    for chunk in chunks:
        assert chunk.text.strip()
        assert chunk.source_path == RUNBOOK
        assert chunk.metadata["doc_type"] == "runbook"
        assert chunk.metadata["service"] == "payment"
        assert chunk.metadata["date"] == "2026-06-02"
        assert chunk.metadata["scenario"] == "latency_spike"
        assert chunk.chunk_id.startswith(f"{RUNBOOK}#")
        assert chunk.metadata["role"] in {"parent", "child"}


def test_heading_becomes_section() -> None:
    chunks = chunk_document(RUNBOOK, repo_root=REPO)
    sections = {chunk.section for chunk in chunks}
    assert any("Immediate checks" in section for section in sections)
    assert any(chunk.heading == chunk.section for chunk in chunks)


def test_adr_002_produces_at_least_one_chunk_with_path_metadata() -> None:
    chunks = chunk_document(ADR_002, repo_root=REPO)
    assert len(chunks) >= 1
    assert all(chunk.text.strip() for chunk in chunks)
    assert all(chunk.source_path == ADR_002 for chunk in chunks)
    assert chunks[0].metadata["doc_type"] == "adr"
    assert chunks[0].metadata["service"] == "platform"
    body = " ".join(chunk.text for chunk in chunks)
    assert "PostgreSQL" in body or "system of record" in body.lower()


def test_chunking_is_deterministic() -> None:
    first = chunk_document(ADR_002, repo_root=REPO)
    second = chunk_document(ADR_002, repo_root=REPO)
    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert [chunk.text for chunk in first] == [chunk.text for chunk in second]


def test_every_allowlisted_file_yields_non_empty_chunks() -> None:
    for rel in ALLOWED_RELATIVE_PATHS:
        chunks = chunk_document(rel, repo_root=REPO)
        assert chunks, f"{rel} produced no chunks"
        assert all(chunk.text.strip() for chunk in chunks)
        assert all(chunk.source_path == rel for chunk in chunks)
        assert all(chunk.section for chunk in chunks)
        assert all(chunk.metadata.get("doc_type") for chunk in chunks)
        assert all(chunk.metadata.get("service") for chunk in chunks)
        assert all(chunk.metadata.get("role") in {"parent", "child"} for chunk in chunks)


def test_corpus_chunker_covers_all_allowlisted_sources() -> None:
    chunks = chunk_allowlisted_corpus(repo_root=REPO)
    sources = {chunk.source_path for chunk in chunks}
    assert sources == set(ALLOWED_RELATIVE_PATHS)


def test_parent_child_links_are_consistent() -> None:
    chunks = chunk_document(ADR_002, repo_root=REPO)
    parents = parent_chunks(chunks)
    children = retrieval_chunks(chunks)
    assert parents
    assert children
    parent_ids = {chunk.chunk_id for chunk in parents}
    assert all(chunk.metadata["role"] == "parent" for chunk in parents)
    assert all(chunk.metadata["role"] == "child" for chunk in children)
    for child in children:
        assert child.metadata["parent_id"] in parent_ids
        parent = next(item for item in parents if item.chunk_id == child.metadata["parent_id"])
        assert child.section == parent.section
        assert len(child.text) <= len(parent.text)


def test_short_section_still_has_one_child() -> None:
    chunks = chunk_document(RUNBOOK, repo_root=REPO)
    children = retrieval_chunks(chunks)
    assert children
    assert all(child.metadata["parent_id"] for child in children)


def test_main_py_is_not_chunked() -> None:
    with pytest.raises(ValueError, match="refuses"):
        chunk_document("src/aegis/main.py", repo_root=REPO)
