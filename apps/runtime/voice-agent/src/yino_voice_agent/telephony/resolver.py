"""Optional HTTP destination lookup. Tests use FakeDestinationResolver."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx

from ..runtime_config import RuntimeConfigurationError
from .inbound import ResolvedDestination

PHONE_LOOKUP_HEADER = "X-Phone-Lookup-Token"


class PlatformDestinationResolver:
    """Consume Platform number lookup. Does not open a database connection.

    Expected JSON object (Contract Change Request if Platform differs):
    tenant_id, voice_agent_instance_id, config_version, enabled.
    """

    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        lookup_token: str | None = None,
    ) -> None:
        self._http = http
        token = (lookup_token or "").strip()
        self._lookup_token = token or None

    async def resolve(self, callee_number: str) -> ResolvedDestination | None:
        if self._lookup_token is None:
            raise RuntimeConfigurationError(
                "destination lookup token is not configured"
            )
        try:
            response = await self._http.get(
                "/api/v1/phone-numbers/lookup",
                params={"number": callee_number},
                headers={PHONE_LOOKUP_HEADER: self._lookup_token},
            )
        except (httpx.TimeoutException, httpx.TransportError, TimeoutError):
            raise RuntimeConfigurationError("destination lookup failed") from None
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise RuntimeConfigurationError(
                f"destination lookup HTTP {response.status_code}"
            )
        try:
            body = response.json()
        except ValueError as error:
            raise RuntimeConfigurationError(
                "destination lookup must be a JSON object"
            ) from error
        if not isinstance(body, dict):
            raise RuntimeConfigurationError("destination lookup must be a JSON object")
        try:
            return _destination_from_lookup(body)
        except RuntimeConfigurationError:
            raise
        except (TypeError, ValueError) as error:
            raise RuntimeConfigurationError("destination lookup is invalid") from error


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
    enabled = body["enabled"]
    if not isinstance(enabled, bool):
        raise RuntimeConfigurationError("destination lookup enabled must be a boolean")
    return ResolvedDestination(
        tenant_id=UUID(str(body["tenant_id"])),
        customer_service_id=UUID(str(body["voice_agent_instance_id"])),
        config_version=int(body["config_version"]),
        enabled=enabled,
    )
