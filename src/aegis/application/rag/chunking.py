"""Parse markdown and emit deterministic chunks (Step 3.2).

Heading-first, then size. No network, no embeddings, no OpenSearch write.
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

# ~400–800 tokens ≈ 1500–3000 characters; overlap ~12%.
TARGET_CHARS = 2200
MAX_CHARS = 3000
OVERLAP_CHARS = 280

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


def chunk_document(path: Path | str, *, repo_root: Path | None = None) -> list[Chunk]:
    """``path → list[Chunk]``. Same file always yields the same chunks."""
    root = (repo_root or repository_root()).resolve()
    rel = assert_allowlisted(path, repo_root=root)
    source = root / rel
    raw = source.read_text(encoding="utf-8")
    body, file_meta = _parse_frontmatter(raw)
    metadata = _document_metadata(rel, file_meta)
    sections = _split_by_heading(body)
    chunks: list[Chunk] = []
    index = 0
    for heading, section_text in sections:
        for piece in _split_by_size(section_text):
            chunks.append(_make_chunk(index, piece, rel, heading, metadata))
            index += 1
    return chunks


def chunk_allowlisted_corpus(*, repo_root: Path | None = None) -> list[Chunk]:
    """Chunk every allowlisted file. Memory only — OpenSearch write is Step 3.4."""
    root = repo_root or repository_root()
    chunks: list[Chunk] = []
    for path in iter_allowlisted_paths(repo_root=root):
        chunks.extend(chunk_document(path, repo_root=root))
    return chunks


def _make_chunk(
    index: int,
    text: str,
    source_path: str,
    section: str,
    metadata: Mapping[str, str],
) -> Chunk:
    digest = hashlib.sha256(f"{source_path}\0{section}\0{text}".encode("utf-8")).hexdigest()[:16]
    return Chunk(
        chunk_id=f"{source_path}#{index:04d}-{digest}",
        text=text,
        source_path=source_path,
        section=section,
        metadata=dict(metadata),
    )


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


def _split_by_size(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= MAX_CHARS:
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
        overlap: list[str] = []
        acc = 0
        for prev in reversed(buf):
            extra = len(prev) if not overlap else len(prev) + 2
            if acc + extra > OVERLAP_CHARS:
                break
            overlap.append(prev)
            acc += extra
        buf = list(reversed(overlap))
        buf_len = sum(len(p) for p in buf) + 2 * max(0, len(buf) - 1)

    for para in paragraphs:
        if len(para) > MAX_CHARS:
            emit()
            windows.extend(_hard_split(para))
            continue
        added = len(para) + (2 if buf else 0)
        if buf and buf_len + added > TARGET_CHARS:
            emit()
        buf.append(para)
        buf_len += len(para) + (2 if buf_len else 0)
    emit()
    return [part for part in windows if part]


def _hard_split(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + TARGET_CHARS, length)
        if end < length:
            window = text[start:end]
            brk = window.rfind("\n")
            if brk >= TARGET_CHARS // 2:
                end = start + brk
        piece = text[start:end].strip()
        if piece:
            parts.append(piece)
        if end >= length:
            break
        start = max(end - OVERLAP_CHARS, start + 1)
    return parts
