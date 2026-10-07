"""Shared Pydantic config: allowlisted fields only (no SSRF gadgets)."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, StringConstraints
from pydantic import ValidationError as PydanticValidationError

from aegis.shared.exceptions import ValidationError

# No path separators, no control characters / NUL. ``..`` is rejected below.
_NO_PATH_CHARS = r"^[^/\\\x00-\x1f\x7f]*$"


def _reject_dot_dot(value: str) -> str:
    if ".." in value:
        raise ValueError("path traversal tokens are not allowed")
    return value


# ``service`` / ``scenario`` end up in catalog keys and filters. They are never a path
# or a URL, so a value that looks like one is an attack, not a typo (Step 5.8 / 5.10).
Service = Annotated[
    str,
    StringConstraints(max_length=255, pattern=_NO_PATH_CHARS),
    AfterValidator(_reject_dot_dot),
]
Scenario = Annotated[
    str,
    StringConstraints(max_length=128, pattern=_NO_PATH_CHARS),
    AfterValidator(_reject_dot_dot),
]


def parse_params(model_type: type, params: object):
    try:
        return model_type.model_validate(dict(params or {}))  # type: ignore[attr-defined]
    except PydanticValidationError as exc:
        raise ValidationError("denied:invalid_params") from exc
