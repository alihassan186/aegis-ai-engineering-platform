"""HTTP opener for tool adapters that never follows redirects (Step 5.10, SSRF).

``urllib`` follows 3xx by default. A hijacked ``:8001`` or OpenSearch could answer
``302 Location: http://169.254.169.254/`` and walk the worker to a new host. Here a
redirect is an ``HTTPError`` instead, which the adapter reports as unavailable.
"""

from __future__ import annotations

import urllib.request
from typing import Any


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


_OPENER = urllib.request.build_opener(_NoRedirect())


def open_no_redirect(request: urllib.request.Request, *, timeout: float) -> Any:
    """Like ``urlopen`` but a 3xx raises ``urllib.error.HTTPError``."""
    return _OPENER.open(request, timeout=timeout)
