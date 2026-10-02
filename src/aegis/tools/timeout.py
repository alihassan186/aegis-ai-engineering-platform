"""Fail-closed timeout around a sync port call."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import TypeVar

from aegis.shared.exceptions import ValidationError

TOOL_TIMEOUT_SECONDS = 10.0

T = TypeVar("T")


def run_with_timeout(fn: Callable[[], T], *, seconds: float = TOOL_TIMEOUT_SECONDS) -> T:
    """Run ``fn`` in a worker thread. On timeout raise ``ValidationError`` (deny)."""
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(fn).result(timeout=seconds)
    except FuturesTimeout as exc:
        raise ValidationError("denied:timeout") from exc
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
