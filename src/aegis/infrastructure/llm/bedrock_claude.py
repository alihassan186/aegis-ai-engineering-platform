"""Claude on Bedrock Runtime. IAM from the environment (NFR-034). No API keys."""

from __future__ import annotations

import json
import re
from typing import Any

from aegis.core.protocols import LlmJsonResult

# ADR-004. Do not put access keys in this module.
CLAUDE_MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class BedrockClaude:
    """``InvokeModel`` for structured RCA JSON. Opt-in via ``AEGIS_LLM=claude``."""

    def __init__(
        self,
        *,
        region: str,
        model_id: str = CLAUDE_MODEL_ID,
        client: Any | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> None:
        if not region.strip():
            raise ValueError("BedrockClaude requires a non-empty AWS region.")
        self._region = region.strip()
        self._model_id = model_id
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._client = client if client is not None else _bedrock_runtime_client(self._region)

    def complete_json(self, *, system: str, user: str) -> LlmJsonResult:
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": self._max_tokens,
                "temperature": self._temperature,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            }
        )
        try:
            response = self._client.invoke_model(
                modelId=self._model_id,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
        except Exception as exc:
            raise ConnectionError(
                "Bedrock Claude InvokeModel failed. Check IAM (bedrock:InvokeModel), "
                f"region {self._region!r}, and that AEGIS_LLM=claude is intended."
            ) from exc
        raw = response["body"].read() if hasattr(response["body"], "read") else response["body"]
        payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        text = _content_text(payload)
        data = _parse_json_object(text)
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        return LlmJsonResult(
            data=data,
            model_id=self._model_id,
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
        )


def _content_text(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if isinstance(content, list):
        parts = [
            str(block.get("text") or "")
            for block in content
            if isinstance(block, dict)
        ]
        return "".join(parts)
    return str(payload.get("completion") or payload.get("output") or "")


def _parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    fenced = _FENCE_RE.search(stripped)
    if fenced:
        stripped = fenced.group(1).strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError("Claude response was not valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Claude JSON must be an object.")
    return parsed


def _bedrock_runtime_client(region: str) -> Any:
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError(
            "boto3 is required when AEGIS_LLM=claude. Install project dependencies."
        ) from exc
    return boto3.client("bedrock-runtime", region_name=region)
