"""Step 3.0 — knowledge corpus is complete and labelled (FR-040, FR-042)."""

from __future__ import annotations

import json
from pathlib import Path

from apps.simulator.scenarios.catalog import ScenarioId

REPO = Path(__file__).resolve().parents[3]
KNOWLEDGE = REPO / "docs" / "knowledge"
RUNBOOKS = KNOWLEDGE / "runbooks"
INCIDENTS = KNOWLEDGE / "incidents"
QUERIES = REPO / "evaluation" / "datasets" / "rag" / "queries.jsonl"

REQUIRED = frozenset({"doc_type", "service", "date", "status"})
SCENARIO_IDS = {item.value for item in ScenarioId}


def _parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise AssertionError(f"{path} must start with YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise AssertionError(f"{path} frontmatter is not closed")
    fields: dict[str, str] = {}
    for raw in text[4:end].splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def _knowledge_markdown() -> list[Path]:
    return sorted(
        path
        for path in KNOWLEDGE.rglob("*.md")
        if path.name != "README.md"
    )


def test_every_knowledge_page_has_required_metadata() -> None:
    pages = _knowledge_markdown()
    assert pages, "docs/knowledge/ has no pages"
    for path in pages:
        meta = _parse_frontmatter(path)
        missing = REQUIRED - set(meta)
        assert not missing, f"{path}: missing {sorted(missing)}"
        assert meta["doc_type"] in {
            "runbook",
            "incident_report",
            "catalog",
            "convention",
        }
        assert meta["service"] in {
            "user",
            "order",
            "payment",
            "inventory",
            "notification",
            "platform",
        }


def test_six_fr083_scenarios_have_runbook_and_rca() -> None:
    runbook_scenarios = {_parse_frontmatter(path)["scenario"] for path in RUNBOOKS.glob("*.md")}
    rca_scenarios = {_parse_frontmatter(path)["scenario"] for path in INCIDENTS.glob("*.md")}
    assert runbook_scenarios == SCENARIO_IDS
    assert rca_scenarios == SCENARIO_IDS
    assert len(list(RUNBOOKS.glob("*.md"))) == 6
    assert len(list(INCIDENTS.glob("*.md"))) == 6


def test_rag_golden_queries_point_at_real_files() -> None:
    rows = [
        json.loads(line)
        for line in QUERIES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) >= 16
    ids = [row["id"] for row in rows]
    assert len(ids) == len(set(ids))
    for row in rows:
        assert row["query"].strip()
        for rel in row["expected_docs"]:
            path = REPO / rel
            assert path.is_file(), f"{row['id']}: missing expected_docs {rel}"
        for rel in row.get("must_not") or []:
            path = REPO / rel
            assert path.is_file(), f"{row['id']}: must_not path missing {rel}"
            assert rel not in row["expected_docs"]
