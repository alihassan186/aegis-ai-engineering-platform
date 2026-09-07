"""Parse markdown into parent/child chunks (Step 3.2).

Parents are heading sections (citation + LLM context). Children are smaller
windows of a parent (hybrid search). No network, no embeddings, no OpenSearch.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from pathlib import Path

from aegis.application.rag.allowlist import (
    assert_allowlisted,
    iter_allowlisted_paths,
    repository_root,
)
from aegis.application.rag.models import Chunk

# Parent ≈ one heading (or a large slice of it) — context for the Knowledge Agent.
PARENT_TARGET_CHARS = 3500
PARENT_MAX_CHARS = 5000
PARENT_OVERLAP_CHARS = 400

# Child ≈ 200–400 tokens — what 3.4 embeds and 3.5 searches.
CHILD_TARGET_CHARS = 800
CHILD_MAX_CHARS = 1200
CHILD_OVERLAP_CHARS = 100

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


def chunk_document(path: Path | str, *, repo_root: Path | None = None) -> list[Chunk]:
    """``path → list[Chunk]`` (parents and children). Same file → same ids."""
    root = (repo_root or repository_root()).resolve()
    rel = assert_allowlisted(path, repo_root=root)
    source = root / rel
    raw = source.read_text(encoding="utf-8")
    body, file_meta = _parse_frontmatter(raw)
    metadata = _document_metadata(rel, file_meta)
    sections = _split_by_heading(body)
    chunks: list[Chunk] = []
    parent_index = 0
    child_index = 0
    for heading, section_text in sections:
        parent_windows = _split_by_size(
            section_text,
            target=PARENT_TARGET_CHARS,
            max_chars=PARENT_MAX_CHARS,
            overlap=PARENT_OVERLAP_CHARS,
        )
        for parent_text in parent_windows:
            parent_id = _chunk_id("p", parent_index, rel, heading, parent_text)
            parent_meta = {**metadata, "role": "parent", "parent_id": parent_id}
            chunks.append(
                Chunk(
                    chunk_id=parent_id,
                    text=parent_text,
                    source_path=rel,
                    section=heading,
                    metadata=parent_meta,
                )
            )
            parent_index += 1
            child_windows = _split_by_size(
                parent_text,
                target=CHILD_TARGET_CHARS,
                max_chars=CHILD_MAX_CHARS,
                overlap=CHILD_OVERLAP_CHARS,
            )
            for child_text in child_windows:
                child_id = _chunk_id("c", child_index, rel, heading, child_text)
                child_meta = {**metadata, "role": "child", "parent_id": parent_id}
                chunks.append(
                    Chunk(
                        chunk_id=child_id,
                        text=child_text,
                        source_path=rel,
                        section=heading,
                        metadata=child_meta,
                    )
                )
                child_index += 1
    return chunks


def chunk_allowlisted_corpus(*, repo_root: Path | None = None) -> list[Chunk]:
    """Chunk every allowlisted file. Memory only — OpenSearch write is Step 3.4."""
    root = repo_root or repository_root()
    chunks: list[Chunk] = []
    for path in iter_allowlisted_paths(repo_root=root):
        chunks.extend(chunk_document(path, repo_root=root))
    return chunks


def retrieval_chunks(chunks: list[Chunk]) -> list[Chunk]:
    """Children only — the units Step 3.4 should embed and Step 3.5 should search."""
    return [chunk for chunk in chunks if chunk.metadata.get("role") == "child"]


def parent_chunks(chunks: list[Chunk]) -> list[Chunk]:
    return [chunk for chunk in chunks if chunk.metadata.get("role") == "parent"]


def _chunk_id(kind: str, index: int, source_path: str, section: str, text: str) -> str:
    digest = hashlib.sha256(f"{source_path}\0{section}\0{text}".encode("utf-8")).hexdigest()[:16]
    return f"{source_path}#{kind}{index:04d}-{digest}"


def _parse_frontmatter(raw: str) -> tuple[str, dict[str, str]]:
    match = _FRONTMATTER.match(raw)
    if not match:
        return raw, {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        fields[key.strip()] = value.strip()
    return raw[match.end() :], fields


def _document_metadata(relative_path: str, frontmatter: Mapping[str, str]) -> dict[str, str]:
    inferred = _metadata_from_path(relative_path)
    merged = dict(inferred)
    for key in ("doc_type", "service", "date", "scenario", "status", "severity", "incident_id"):
        value = frontmatter.get(key, "").strip()
        if value:
            merged[key] = value
    if "related_services" in frontmatter and frontmatter["related_services"].strip():
        merged["related_services"] = frontmatter["related_services"].strip()
    return merged


def _metadata_from_path(relative_path: str) -> dict[str, str]:
    parts = relative_path.split("/")
    kind = parts[1] if len(parts) > 1 and parts[0] == "docs" else "document"
    aliases = {"releases": "release"}
    return {"doc_type": aliases.get(kind, kind), "service": "platform"}


def _split_by_heading(body: str) -> list[tuple[str, str]]:
    current = "lead"
    lines: list[str] = []
    sections: list[tuple[str, str]] = []

    def flush() -> None:
        text = "\n".join(lines).strip()
        if text:
            sections.append((current, text))

    for line in body.splitlines():
        heading = _HEADING.match(line)
        if heading:
            flush()
            current = heading.group(2).strip()
            lines = [line]
            continue
        lines.append(line)
    flush()
    return sections or [("lead", body.strip())] if body.strip() else []


def _split_by_size(
    text: str,
    *,
    target: int,
    max_chars: int,
    overlap: int,
) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    windows: list[str] = []
    buf: list[str] = []
    buf_len = 0

    def emit() -> None:
        nonlocal buf, buf_len
        if not buf:
            return
        windows.append("\n\n".join(buf))
        overlap_parts: list[str] = []
        acc = 0
        for prev in reversed(buf):
            extra = len(prev) if not overlap_parts else len(prev) + 2
            if acc + extra > overlap:
                break
            overlap_parts.append(prev)
            acc += extra
        buf = list(reversed(overlap_parts))
        buf_len = sum(len(p) for p in buf) + 2 * max(0, len(buf) - 1)

    for para in paragraphs:
        if len(para) > max_chars:
            emit()
            windows.extend(_hard_split(para, target=target, overlap=overlap))
            continue
        added = len(para) + (2 if buf else 0)
        if buf and buf_len + added > target:
            emit()
        buf.append(para)
        buf_len += len(para) + (2 if buf_len else 0)
    emit()
    return [part for part in windows if part]


def _hard_split(text: str, *, target: int, overlap: int) -> list[str]:
    parts: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + target, length)
        if end < length:
            window = text[start:end]
            brk = window.rfind("\n")
            if brk >= target // 2:
                end = start + brk
        piece = text[start:end].strip()
        if piece:
            parts.append(piece)
        if end >= length:
            break
        start = max(end - overlap, start + 1)
    return parts
