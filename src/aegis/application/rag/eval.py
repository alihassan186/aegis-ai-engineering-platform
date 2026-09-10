"""Score evaluation/datasets/rag/queries.jsonl (RAG eval, not FR-090 RCA)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from aegis.application.rag.allowlist import repository_root
from aegis.application.rag.retrieve import (
    RetrieveFilters,
    RetrieveHit,
    RetrieveKnowledge,
)

EVAL_TOP_K = 8
EVAL_RELATIVE_PATH = "evaluation/datasets/rag/queries.jsonl"


@dataclass(frozen=True, slots=True)
class EvalCase:
    id: str
    query: str
    filters: RetrieveFilters
    expected_docs: tuple[str, ...]
    must_not: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EvalCaseResult:
    case_id: str
    passed: bool
    missing: tuple[str, ...]
    forbidden_hits: tuple[str, ...]
    documents: tuple[str, ...]


def load_eval_cases(*, repo_root: Path | None = None) -> list[EvalCase]:
    root = (repo_root or repository_root()).resolve()
    path = root / EVAL_RELATIVE_PATH
    cases: list[EvalCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        raw = json.loads(stripped)
        filters = raw.get("filters") or {}
        cases.append(
            EvalCase(
                id=str(raw["id"]),
                query=str(raw["query"]),
                filters=RetrieveFilters(
                    service=filters.get("service"),
                    doc_type=filters.get("doc_type"),
                    scenario=filters.get("scenario"),
                    date_from=filters.get("date_from"),
                    date_to=filters.get("date_to"),
                    incident_id=filters.get("incident_id"),
                ),
                expected_docs=tuple(raw.get("expected_docs") or ()),
                must_not=tuple(raw.get("must_not") or ()),
            )
        )
    return cases


def score_eval_case(
    retrieve: RetrieveKnowledge,
    case: EvalCase,
    *,
    top_k: int = EVAL_TOP_K,
) -> EvalCaseResult:
    result = retrieve.execute(case.query, filters=case.filters, top_k=top_k)
    documents = tuple(_hit_documents(result.hits))
    missing = tuple(doc for doc in case.expected_docs if doc not in documents)
    forbidden = tuple(doc for doc in case.must_not if doc in documents)
    return EvalCaseResult(
        case_id=case.id,
        passed=not missing and not forbidden,
        missing=missing,
        forbidden_hits=forbidden,
        documents=documents,
    )


def score_eval_dataset(
    retrieve: RetrieveKnowledge,
    cases: Sequence[EvalCase] | None = None,
    *,
    top_k: int = EVAL_TOP_K,
    repo_root: Path | None = None,
) -> list[EvalCaseResult]:
    loaded = list(cases) if cases is not None else load_eval_cases(repo_root=repo_root)
    return [score_eval_case(retrieve, case, top_k=top_k) for case in loaded]


def _hit_documents(hits: Sequence[RetrieveHit]) -> list[str]:
    seen: list[str] = []
    for hit in hits:
        document = hit.citation.document
        if document not in seen:
            seen.append(document)
    return seen
