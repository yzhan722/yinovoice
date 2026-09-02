"""Fake telephony inbound seam. No real SIP, PSTN, or provider network."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import UUID

from ..runtime_config import DispatchMetadata, RuntimeConfigurationError


@dataclass(frozen=True, slots=True)
class NormalizedInboundCall:
    provider: str
    provider_call_id: str
    caller_number: str | None
    callee_number: str
    direction: Literal["inbound"]
    connected_at: datetime
    room_name: str | None = None


@dataclass(frozen=True, slots=True)
class ResolvedDestination:
    tenant_id: UUID
    customer_service_id: UUID
    config_version: int
    enabled: bool


class DestinationResolver(Protocol):
    async def resolve(self, callee_number: str) -> ResolvedDestination | None:
        """Map a callee number to a Platform destination. None = unknown."""


class FakeDestinationResolver:
    def __init__(
        self,
        destinations: dict[str, ResolvedDestination],
    ) -> None:
        self._destinations = destinations

    async def resolve(self, callee_number: str) -> ResolvedDestination | None:
        return self._destinations.get(callee_number)


class FakeInboundProvider:
    """Deterministic inbound events. Duplicate provider_call_id is ignored."""

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()

    def ingest(
        self,
        *,
        provider: str,
        provider_call_id: str,
        callee_number: str,
        caller_number: str | None = None,
        room_name: str | None = None,
        connected_at: datetime | None = None,
    ) -> NormalizedInboundCall | None:
        if not provider_call_id.strip() or not callee_number.strip():
            return None
        if provider_call_id in self._seen_ids:
            return None
        self._seen_ids.add(provider_call_id)
        return NormalizedInboundCall(
            provider=provider,
            provider_call_id=provider_call_id,
            caller_number=caller_number,
            callee_number=callee_number,
            direction="inbound",
            connected_at=connected_at or datetime.now(UTC),
            room_name=room_name,
        )


class RuntimeDispatch:
    """Translate a resolved inbound call into current Agent dispatch metadata."""

    @staticmethod
    def to_metadata(
        call: NormalizedInboundCall,
        destination: ResolvedDestination,
    ) -> DispatchMetadata:
        if not destination.enabled:
            raise RuntimeConfigurationError("destination is disabled")
        return DispatchMetadata(
            customer_service_id=destination.customer_service_id,
            tenant_id=destination.tenant_id,
            config_version=destination.config_version,
            channel="sip",
            caller_number=call.caller_number,
            callee_number=call.callee_number,
            provider_call_id=call.provider_call_id,
        )


class InboundCallAdapter:
    def __init__(
        self,
        *,
        provider: FakeInboundProvider,
        resolver: DestinationResolver,
    ) -> None:
        self._provider = provider
        self._resolver = resolver

    async def dispatch(
        self,
        *,
        provider: str,
        provider_call_id: str,
        callee_number: str,
        caller_number: str | None = None,
        room_name: str | None = None,
    ) -> DispatchMetadata | None:
        call = self._provider.ingest(
            provider=provider,
            provider_call_id=provider_call_id,
            callee_number=callee_number,
            caller_number=caller_number,
            room_name=room_name,
        )
        if call is None:
            return None
        destination = await self._resolver.resolve(call.callee_number)
        if destination is None or not destination.enabled:
            return None
        return RuntimeDispatch.to_metadata(call, destination)
