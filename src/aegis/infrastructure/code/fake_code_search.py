"""In-process code/deploy catalog (FR-013, FR-014). No GitHub token, no ``src/`` walk."""

from __future__ import annotations

from aegis.core.protocols import CodeHit

# Deliberate catalog — not a filesystem search of src/aegis.
_DEPLOY_VERSIONS: dict[str, str] = {
    "user": "1.14.0",
    "payment": "2.8.1",
    "order": "3.1.0",
    "inventory": "1.0.4",
    "notification": "0.9.2",
}


class FakeCodeSearch:
    """v0.5 stand-in until Phase 5 wraps GitHub through the tool gateway."""

    def recent_deploys(self, *, service: str) -> list[CodeHit]:
        key = service.strip().lower() or "user"
        version = _DEPLOY_VERSIONS.get(key, "0.0.0")
        return [
            CodeHit(
                service=key,
                version=version,
                path=f"services/{key}/deployments.md",
                summary=f"last deploy of {key} was {version}",
            )
        ]

    def search(self, *, service: str, scenario: str) -> list[CodeHit]:
        deploys = self.recent_deploys(service=service)
        key = service.strip().lower() or "user"
        return [
            *deploys,
            CodeHit(
                service=key,
                version=deploys[0].version,
                path=f"services/{key}/app.py",
                summary=f"recent change in services/{key} related to {scenario}",
            ),
        ]
