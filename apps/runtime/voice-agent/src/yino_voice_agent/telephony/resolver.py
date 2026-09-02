"""Optional HTTP destination lookup. Tests use FakeDestinationResolver."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx

from ..runtime_config import RuntimeConfigurationError
from .inbound import ResolvedDestination


class PlatformDestinationResolver:
    """Consume Platform number lookup. Does not open a database connection.

    Expected JSON object (Contract Change Request if Platform differs):
    tenant_id, voice_agent_instance_id, config_version, enabled.
    """

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def resolve(self, callee_number: str) -> ResolvedDestination | None:
        response = await self._http.get(
            "/api/v1/phone-numbers/lookup",
            params={"number": callee_number},
        )
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise RuntimeConfigurationError(
                f"destination lookup HTTP {response.status_code}"
            )
        body = response.json()
        if not isinstance(body, dict):
            raise RuntimeConfigurationError("destination lookup must be a JSON object")
        return _destination_from_lookup(body)


def _destination_from_lookup(body: dict[str, Any]) -> ResolvedDestination:
    required = (
        "tenant_id",
        "voice_agent_instance_id",
        "config_version",
        "enabled",
    )
    missing = [key for key in required if key not in body]
    if missing:
        raise RuntimeConfigurationError(
            "destination lookup missing fields: " + ", ".join(missing)
        )
    return ResolvedDestination(
        tenant_id=UUID(str(body["tenant_id"])),
        customer_service_id=UUID(str(body["voice_agent_instance_id"])),
        config_version=int(body["config_version"]),
        enabled=bool(body["enabled"]),
    )
