"""HMAC-SHA256 webhook signatures (THR-002).

Keep the digest format in lockstep with ``apps.simulator.aegis_client.sign_body``.
IP allowlisting from THR-002 is a follow-up, not implemented in v0.3.
"""

from __future__ import annotations

import hashlib
import hmac

SIGNATURE_HEADER = "X-Aegis-Signature"
_PREFIX = "sha256="


def compute_signature(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"{_PREFIX}{digest}"


def verify_signature(secret: str, body: bytes, provided: str | None) -> bool:
    if not secret or not provided:
        return False
    expected = compute_signature(secret, body)
    return hmac.compare_digest(expected, provided.strip())
