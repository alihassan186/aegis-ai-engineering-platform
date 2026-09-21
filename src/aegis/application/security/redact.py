"""DLP-lite secret redaction (FR-019, THR-009).

Pure functions — no I/O, no boto3, no logging of the pre-image.
Evidence persist and the 4.8 prompt assembler (and later the tool
gateway) must call this same helper. Not a full DLP product.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

_MARKER_PREFIX = "[REDACTED:"


@dataclass(frozen=True, slots=True)
class RedactionResult:
    """Redacted text plus how many substitutions were made."""

    text: str
    count: int
    kinds: tuple[str, ...]

    @property
    def redacted(self) -> bool:
        return self.count > 0


def _token(kind: str) -> str:
    return f"{_MARKER_PREFIX}{kind}]"


# Fail closed: if it looks like a key, replace the whole match.
# Order is longest / most specific first so a PEM is not picked apart as JWT.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private_key",
        re.compile(
            r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"
            r".*?"
            r"-----END (?:[A-Z]+ )?PRIVATE KEY-----",
            re.DOTALL,
        ),
    ),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{8,}\b"),
    ),
    (
        "database_url",
        re.compile(
            r"(?i)\b(?:postgres(?:ql)?(?:\+[a-z0-9]+)?)://"
            r"[^:\s/]+:[^@\s/]+@[^\s]+"
        ),
    ),
    ("bearer_token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-+/=]{8,}")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    (
        "github_pat",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    ),
    (
        "email",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ),
)


def redact(text: str) -> RedactionResult:
    """Replace detected secrets with ``[REDACTED:<kind>]``. Never logs input."""
    if not text:
        return RedactionResult(text=text, count=0, kinds=())
    current = text
    kinds: list[str] = []
    total = 0
    for kind, pattern in _PATTERNS:

        def _replace(_match: re.Match[str], *, _kind: str = kind) -> str:
            nonlocal total
            total += 1
            kinds.append(_kind)
            return _token(_kind)

        current = pattern.sub(_replace, current)
    return RedactionResult(text=current, count=total, kinds=tuple(kinds))


def redact_for_llm(text: str) -> str:
    """Same redactor, text-only. Reserved for Step 4.8 context assembly."""
    return redact(text).text


def redact_mapping(value: Any) -> tuple[Any, int]:
    """Redact string leaves in JSON-shaped metadata. Embeddings stay out."""
    if isinstance(value, str):
        result = redact(value)
        return result.text, result.count
    if isinstance(value, Mapping):
        total = 0
        out: dict[str, Any] = {}
        for key, item in value.items():
            redacted, count = redact_mapping(item)
            out[str(key)] = redacted
            total += count
        return out, total
    if isinstance(value, list):
        total = 0
        out_list: list[Any] = []
        for item in value:
            redacted, count = redact_mapping(item)
            out_list.append(redacted)
            total += count
        return out_list, total
    return value, 0


def marker_count(*parts: str) -> int:
    """How many redaction markers remain (safe to store; not the pre-image)."""
    return sum(part.count(_MARKER_PREFIX) for part in parts)
