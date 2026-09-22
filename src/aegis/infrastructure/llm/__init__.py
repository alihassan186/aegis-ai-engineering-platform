"""LLM adapters. Application code depends on ``LlmClient``, not these classes."""

from aegis.config.settings import Settings
from aegis.core.protocols import LlmClient
from aegis.infrastructure.llm.bedrock_claude import BedrockClaude
from aegis.infrastructure.llm.fake_llm import FakeLlm


def build_llm(settings: Settings | None = None) -> LlmClient:
    """Compose Fake vs Claude from env. Default is fake (tests / local)."""
    resolved = settings or Settings.from_env()
    if resolved.llm == "fake":
        return FakeLlm()
    if resolved.llm == "claude":
        if not resolved.aws_region:
            raise ValueError("AEGIS_AWS_REGION (or AWS_REGION) is required when AEGIS_LLM=claude.")
        return BedrockClaude(region=resolved.aws_region)
    raise ValueError(f"Unknown llm {resolved.llm!r}; use fake or claude.")


__all__ = ["BedrockClaude", "FakeLlm", "build_llm"]
