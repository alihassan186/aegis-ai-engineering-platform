"""Deployable HTTP API process.

This module does not define routes. It imports the app from the core package.

    uvicorn aegis.main:app --reload
    uvicorn apps.api.main:app --reload
"""

from aegis.main import app

__all__ = ["app"]
