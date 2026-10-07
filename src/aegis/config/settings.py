"""Application settings for local, test, and production environments."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_ENVIRONMENT_NAMES = {"development", "test", "production"}
_ASYNC_POSTGRES_PREFIX = "postgresql+asyncpg://"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_TRUTHY = {"1", "true", "yes", "on"}
DEFAULT_TOOL_ALLOWED_HOSTS: tuple[str, ...] = (
    "127.0.0.1:8001",
    "localhost:8001",
    "127.0.0.1:9200",
    "localhost:9200",
)


def _load_dotenv_file() -> None:
    """Load repo-root `.env` into os.environ without overriding existing vars.

    Uvicorn does not read `.env` by itself. Tests set AEGIS_SKIP_DOTENV=1 so
    fixtures stay in control of the environment.
    """
    if os.getenv("AEGIS_SKIP_DOTENV") == "1":
        return
    path = _REPO_ROOT / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    """Environment-aware settings container.

    Secrets and connection strings come from the process environment
    (NFR-032, THR-013). Never hardcode credentials here.
    """

    environment: str = "development"
    debug: bool = False
    app_name: str = "aegis"
    log_level: str = "INFO"
    database_url: str = ""
    jwt_secret: str = ""
    jwt_expire_seconds: int = 3600
    webhook_secret: str = ""
    opensearch_url: str = ""
    embedder: str = "fake"
    aws_region: str = ""
    aws_endpoint: str = ""
    event_bus_name: str = "aegis-events"
    investigation_queue_name: str = "investigation-workflow"
    notification_queue_name: str = "notification"
    simulator_base_url: str = "http://127.0.0.1:8001"
    llm: str = "fake"
    tool_rate_window_seconds: int = 60
    tool_rate_per_tool_incident: int = 30
    tool_rate_per_agent: int = 90
    tool_rate_fail_closed: bool = False
    tool_timeout_seconds: float = 10.0
    tool_max_output_bytes: int = 32768
    tool_max_param_bytes: int = 16384
    tool_breaker_threshold: int = 3
    tool_breaker_cooldown_seconds: float = 30.0
    tool_allowed_hosts: tuple[str, ...] = DEFAULT_TOOL_ALLOWED_HOSTS
    guardrail_deny_all: bool = False

    @classmethod
    def from_env(cls) -> Settings:
        _load_dotenv_file()
        environment = os.getenv("AEGIS_ENV", "development").lower()
        if environment not in _ENVIRONMENT_NAMES:
            environment = "development"

        database_url = os.getenv("AEGIS_DATABASE_URL", "").strip()
        if database_url and not database_url.startswith(_ASYNC_POSTGRES_PREFIX):
            raise ValueError(
                "AEGIS_DATABASE_URL must use the postgresql+asyncpg:// driver prefix (ADR-002)."
            )
        jwt_secret = os.getenv("AEGIS_JWT_SECRET", "").strip()
        jwt_expire_seconds = _parse_positive_int(
            os.getenv("AEGIS_JWT_EXPIRE_SECONDS"),
            default=3600,
        )
        webhook_secret = os.getenv("AEGIS_WEBHOOK_SECRET", "").strip()
        opensearch_url = os.getenv("AEGIS_OPENSEARCH_URL", "").strip().rstrip("/")
        embedder = _parse_embedder_name(os.getenv("AEGIS_EMBEDDER"))
        aws_region = (
            os.getenv("AEGIS_AWS_REGION", "").strip() or os.getenv("AWS_REGION", "").strip()
        )
        aws_endpoint = os.getenv("AEGIS_AWS_ENDPOINT", "").strip().rstrip("/")
        event_bus_name = os.getenv("AEGIS_EVENT_BUS_NAME", "").strip() or "aegis-events"
        investigation_queue_name = (
            os.getenv("AEGIS_INVESTIGATION_QUEUE_NAME", "").strip() or "investigation-workflow"
        )
        notification_queue_name = (
            os.getenv("AEGIS_NOTIFICATION_QUEUE_NAME", "").strip() or "notification"
        )
        simulator_base_url = (
            os.getenv("AEGIS_SIMULATOR_URL", "").strip().rstrip("/") or "http://127.0.0.1:8001"
        )
        llm = _parse_llm_name(os.getenv("AEGIS_LLM"))
        tool_rate_window_seconds = _parse_positive_int(
            os.getenv("AEGIS_TOOL_RATE_WINDOW_SECONDS"),
            default=60,
        )
        tool_rate_per_tool_incident = _parse_positive_int(
            os.getenv("AEGIS_TOOL_RATE_PER_TOOL_INCIDENT"),
            default=30,
        )
        tool_rate_per_agent = _parse_positive_int(
            os.getenv("AEGIS_TOOL_RATE_PER_AGENT"),
            default=90,
        )
        fail_closed_raw = os.getenv("AEGIS_TOOL_RATE_FAIL_CLOSED", "").strip().lower()
        if fail_closed_raw in {"1", "true", "yes", "on"}:
            tool_rate_fail_closed = True
        elif fail_closed_raw in {"0", "false", "no", "off"}:
            tool_rate_fail_closed = False
        else:
            tool_rate_fail_closed = environment == "production"
        tool_timeout_seconds = _parse_positive_float(
            os.getenv("AEGIS_TOOL_TIMEOUT_SECONDS"),
            default=10.0,
        )
        tool_max_output_bytes = _parse_positive_int(
            os.getenv("AEGIS_TOOL_MAX_OUTPUT_BYTES"),
            default=32768,
        )
        tool_max_param_bytes = _parse_positive_int(
            os.getenv("AEGIS_TOOL_MAX_PARAM_BYTES"),
            default=16384,
        )
        tool_breaker_threshold = _parse_positive_int(
            os.getenv("AEGIS_TOOL_BREAKER_THRESHOLD"),
            default=3,
        )
        tool_breaker_cooldown_seconds = _parse_positive_float(
            os.getenv("AEGIS_TOOL_BREAKER_COOLDOWN_SECONDS"),
            default=30.0,
        )
        tool_allowed_hosts = _parse_host_list(os.getenv("AEGIS_TOOL_ALLOWED_HOSTS"))

        if environment == "production" and not database_url:
            raise ValueError("AEGIS_DATABASE_URL is required when AEGIS_ENV=production (NFR-060).")
        if environment == "production" and not jwt_secret:
            raise ValueError("AEGIS_JWT_SECRET is required when AEGIS_ENV=production (THR-013).")
        if environment == "production" and not webhook_secret:
            raise ValueError(
                "AEGIS_WEBHOOK_SECRET is required when AEGIS_ENV=production (THR-002)."
            )

        return cls(
            environment=environment,
            debug=os.getenv("AEGIS_DEBUG", "false").lower() in {"1", "true", "yes", "on"},
            app_name=os.getenv("AEGIS_APP_NAME", "aegis"),
            log_level=os.getenv("AEGIS_LOG_LEVEL", "INFO").upper(),
            database_url=database_url,
            jwt_secret=jwt_secret,
            jwt_expire_seconds=jwt_expire_seconds,
            webhook_secret=webhook_secret,
            opensearch_url=opensearch_url,
            embedder=embedder,
            aws_region=aws_region,
            aws_endpoint=aws_endpoint,
            event_bus_name=event_bus_name,
            investigation_queue_name=investigation_queue_name,
            notification_queue_name=notification_queue_name,
            simulator_base_url=simulator_base_url,
            llm=llm,
            tool_rate_window_seconds=tool_rate_window_seconds,
            tool_rate_per_tool_incident=tool_rate_per_tool_incident,
            tool_rate_per_agent=tool_rate_per_agent,
            tool_rate_fail_closed=tool_rate_fail_closed,
            tool_timeout_seconds=tool_timeout_seconds,
            tool_max_output_bytes=tool_max_output_bytes,
            tool_max_param_bytes=tool_max_param_bytes,
            tool_breaker_threshold=tool_breaker_threshold,
            tool_breaker_cooldown_seconds=tool_breaker_cooldown_seconds,
            tool_allowed_hosts=tool_allowed_hosts,
            guardrail_deny_all=guardrail_deny_all_enabled(),
        )


def get_settings() -> Settings:
    return Settings.from_env()


def guardrail_deny_all_enabled() -> bool:
    """Kill switch (Step 5.11). Read from the environment on every call.

    Deliberately not cached: flipping ``AEGIS_GUARDRAIL_DENY_ALL`` takes effect
    on the next ``invoke`` without a deploy. It is an operator env var only. It
    is never read from tool parameters, incident comments, or the LLM prompt.
    """
    return os.getenv("AEGIS_GUARDRAIL_DENY_ALL", "").strip().lower() in _TRUTHY


def _parse_positive_int(raw: str | None, *, default: int) -> int:
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _parse_positive_float(raw: str | None, *, default: float) -> float:
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _parse_host_list(raw: str | None) -> tuple[str, ...]:
    """Comma separated ``host:port`` allowlist for tool HTTP adapters (5.10)."""
    if raw is None or not raw.strip():
        return DEFAULT_TOOL_ALLOWED_HOSTS
    hosts = tuple(
        item.strip().lower() for item in raw.split(",") if item.strip()
    )
    return hosts or DEFAULT_TOOL_ALLOWED_HOSTS


def _parse_embedder_name(raw: str | None) -> str:
    """Default fake so tests and local ingest run without AWS (Step 3.3)."""
    name = (raw or "").strip().lower()
    if not name:
        return "fake"
    if name in {"fake", "titan"}:
        return name
    raise ValueError("AEGIS_EMBEDDER must be 'fake' or 'titan'.")


def _parse_llm_name(raw: str | None) -> str:
    """Default fake so CI and local graph runs never need Bedrock (Step 4.8)."""
    name = (raw or "").strip().lower()
    if not name:
        return "fake"
    if name in {"fake", "claude"}:
        return name
    raise ValueError("AEGIS_LLM must be 'fake' or 'claude'.")
