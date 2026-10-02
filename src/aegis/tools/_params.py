"""Shared Pydantic config: allowlisted fields only (no SSRF gadgets)."""

from __future__ import annotations

from pydantic import ValidationError as PydanticValidationError

from aegis.shared.exceptions import ValidationError


def parse_params(model_type: type, params: object):
    try:
        return model_type.model_validate(dict(params or {}))  # type: ignore[attr-defined]
    except PydanticValidationError as exc:
        raise ValidationError("denied:invalid_params") from exc
