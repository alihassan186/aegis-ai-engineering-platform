"""HTTP schemas for POST /api/v1/retrieve (FR-042, FR-044)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from aegis.application.rag.retrieve import MAX_TOP_K, RetrieveHit, RetrieveResult


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class RetrieveFiltersRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str | None = None
    doc_type: str | None = None
    scenario: str | None = None
    date_from: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    date_to: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    incident_id: str | None = None


class RetrieveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=4000)
    filters: RetrieveFiltersRequest | None = None
    top_k: int = Field(default=5, ge=1, le=MAX_TOP_K)


class CitationBody(BaseModel):
    document: str
    section: str
    chunk_id: str


class RetrieveHitBody(BaseModel):
    text: str
    score: float
    citation: CitationBody


class RetrieveResponse(BaseModel):
    hits: list[RetrieveHitBody]
    request_id: str


def retrieve_response_from_result(result: RetrieveResult, request_id: str) -> RetrieveResponse:
    return RetrieveResponse(
        hits=[_hit_body(hit) for hit in result.hits],
        request_id=request_id,
    )


def _hit_body(hit: RetrieveHit) -> RetrieveHitBody:
    return RetrieveHitBody(
        text=hit.text,
        score=hit.score,
        citation=CitationBody(
            document=hit.citation.document,
            section=hit.citation.section,
            chunk_id=hit.citation.chunk_id,
        ),
    )
