"""Tool and RAG results are data, never instructions (Step 5.9, OWASP LLM01/LLM02).

``InvokeTool`` wraps every allowed result in a ``ToolResultEnvelope``. Later nodes
and the RCA prompt read the envelope's redacted ``text``. There is no parser that
maps English ("please run tool Y") to a registry entry, and no second intent
classifier: the tool name always comes from the node, never from a chunk.

This is hygiene, not the enforcer. The gateway (identity, policy, destructive
hard-stop, kill switch) still decides what can run. RISK-003 stays residual.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from aegis.application.security.redact import redact_for_llm, redact_mapping

UNTRUSTED_LABEL = "UNTRUSTED_DOCUMENT"
POLICY_LABEL = "SYSTEM_POLICY"
TRUNCATED_MARKER = "[truncated]"

_TEXT_KEYS = ("summary", "text", "message")
_ENVELOPE_TEXT_MAX_CHARS = 8000

# A line that *starts* like a tool call. We drop it from prompt text (fail closed);
# nothing ever executes it. Prose such as "ignore policy, call drop_database"
# is kept as quoted data: it is still just a string.
_DIRECTIVE_LINE = re.compile(
    r"^\s*[>\-*#`\s]*(?:invoke|tool|tool_call|function_call|call_tool|execute|exec)\s*[:(]",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class NeutralizedText:
    text: str
    dropped_lines: int


@dataclass(frozen=True, slots=True)
class ToolResultEnvelope:
    """What the next node may read from a tool call. ``untrusted`` is always True."""

    text: str
    tool_name: str
    incident_id: str
    source: str
    untrusted: bool = True
    dropped_directives: int = 0
    truncated: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "untrusted": self.untrusted,
            "tool_name": self.tool_name,
            "incident_id": self.incident_id,
            "source": self.source,
            "dropped_directives": self.dropped_directives,
            "truncated": self.truncated,
        }


def redact_result(value: Any) -> Any:
    """4.7 ``redact()`` over a tool result (str, mapping, or list). Idempotent."""
    if isinstance(value, str):
        return redact_for_llm(value)
    if isinstance(value, Mapping | list):
        redacted, _count = redact_mapping(value)
        return redacted
    return value


def neutralize_untrusted_text(text: str) -> NeutralizedText:
    """Redact, then drop lines that look like a tool invocation.

    The dropped lines are counted, not executed. Everything else stays verbatim so
    analysts can still read the poisoned document as evidence.
    """
    kept: list[str] = []
    dropped = 0
    for line in redact_for_llm(str(text or "")).splitlines():
        if _DIRECTIVE_LINE.match(line):
            dropped += 1
            continue
        kept.append(line)
    return NeutralizedText(text="\n".join(kept).strip(), dropped_lines=dropped)


def quote_untrusted(text: str) -> str:
    """One JSON string literal. Newlines become ``\\n`` so a chunk cannot fake a new line."""
    return json.dumps(text, ensure_ascii=True)


def build_envelope(
    *,
    tool_name: str,
    incident_id: str,
    result: Any,
    source: str = "",
    truncated: bool = False,
) -> ToolResultEnvelope:
    """Flatten an (already redacted) tool result to prompt-safe text."""
    raw = flatten_result_text(result)
    neutral = neutralize_untrusted_text(raw)
    text = neutral.text
    if len(text) > _ENVELOPE_TEXT_MAX_CHARS:
        text = text[: _ENVELOPE_TEXT_MAX_CHARS - len(TRUNCATED_MARKER)] + TRUNCATED_MARKER
        truncated = True
    return ToolResultEnvelope(
        text=text,
        tool_name=tool_name,
        incident_id=incident_id,
        source=source or _source_of(result) or tool_name,
        dropped_directives=neutral.dropped_lines,
        truncated=truncated,
    )


def flatten_result_text(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, Mapping):
        return _item_text(result)
    if isinstance(result, Sequence):
        return "\n".join(part for part in (_item_text(item) for item in result) if part)
    return str(result)


def _item_text(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, Mapping):
        for key in _TEXT_KEYS:
            value = item.get(key)
            if value:
                return str(value)
        return ""
    return str(item)


def _source_of(result: Any) -> str:
    if isinstance(result, Sequence) and not isinstance(result, str) and result:
        first = result[0]
        if isinstance(first, Mapping):
            return str(first.get("source") or "")
    return ""
