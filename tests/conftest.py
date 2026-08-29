"""Suite-wide pytest defaults. Loaded before test modules import the app."""

from __future__ import annotations

import os

# Stop Settings.from_env() from reading the developer `.env` during tests.
os.environ["AEGIS_SKIP_DOTENV"] = "1"
