"""Chunk read model for ingest (FR-040) and later citations (FR-044)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class Chunk:
    """One retrieval unit. ``section`` is the markdown heading (citation heading).

    ``metadata`` includes frontmatter plus ``role`` (parent|child) and ``parent_id``.
    """

    chunk_id: str
    text: str
    source_path: str
    section: str
    metadata: Mapping[str, str]

    @property
    def heading(self) -> str:
        """Section heading. Same as ``section``."""
        return self.section
