"""AEGIS HTTP API entrypoint.

Run with::

    uvicorn aegis.main:app --reload
"""

from aegis.main import app

__all__ = ["app"]
