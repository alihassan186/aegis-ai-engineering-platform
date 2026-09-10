"""v0.4 allowlist is exactly 24 paths; everything else is refused."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegis.application.rag.allowlist import (
    ALLOWED_RELATIVE_PATHS,
    assert_allowlisted,
    is_allowlisted,
    iter_allowlisted_paths,
    repository_root,
)

REPO = repository_root()


def test_allowlist_has_exactly_twenty_four_existing_files() -> None:
    assert len(ALLOWED_RELATIVE_PATHS) == 24
    assert len(set(ALLOWED_RELATIVE_PATHS)) == 24
    for rel in ALLOWED_RELATIVE_PATHS:
        assert (REPO / rel).is_file(), f"missing allowlisted file {rel}"


def test_allowlist_includes_exactly_six_written_rcas() -> None:
    rcas = [
        path
        for path in ALLOWED_RELATIVE_PATHS
        if path.startswith("docs/knowledge/incidents/INC-2026-")
    ]
    assert len(rcas) == 6
    assert all(path.endswith(".md") for path in rcas)


def test_iter_allowlisted_paths_matches_the_tuple() -> None:
    paths = iter_allowlisted_paths(repo_root=REPO)
    assert len(paths) == 24
    assert [path.relative_to(REPO).as_posix() for path in paths] == list(ALLOWED_RELATIVE_PATHS)


def test_src_main_is_rejected() -> None:
    main = REPO / "src" / "aegis" / "main.py"
    assert main.is_file()
    assert is_allowlisted(main, repo_root=REPO) is False
    with pytest.raises(ValueError, match="refuses"):
        assert_allowlisted(main, repo_root=REPO)


@pytest.mark.parametrize(
    "relative",
    [
        "docs/implementation-guide.md",
        "docs/requirements/functional-requirements.md",
        "evaluation/datasets/rag/queries.jsonl",
        "apps/simulator/main.py",
        ".env",
    ],
)
def test_out_of_scope_paths_are_rejected(relative: str) -> None:
    assert is_allowlisted(Path(relative), repo_root=REPO) is False
