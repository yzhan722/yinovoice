from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from ..domain.phone_number import PhoneNumber, PhoneNumberCreate


class PhoneNumberConflict(Exception):  # noqa: N818
    """Raised when an E.164 number is already mapped."""


class PhoneNumberRepository(Protocol):
    async def list_for_tenant(self, tenant_id: UUID) -> list[PhoneNumber]: ...

    async def get(
        self, phone_number_id: UUID, tenant_id: UUID
    ) -> PhoneNumber | None: ...

    async def get_by_e164(self, e164_number: str) -> PhoneNumber | None: ...

    async def create(
        self, tenant_id: UUID, payload: PhoneNumberCreate
    ) -> PhoneNumber: ...

    async def save(self, number: PhoneNumber) -> PhoneNumber: ...

    async def delete(self, phone_number_id: UUID, tenant_id: UUID) -> bool: ...


class InMemoryPhoneNumberRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[UUID, UUID], PhoneNumber] = {}

    def _find_e164(self, e164_number: str) -> PhoneNumber | None:
        matches = [
            item for item in self._items.values() if item.e164_number == e164_number
        ]
        return matches[0] if matches else None

    async def list_for_tenant(self, tenant_id: UUID) -> list[PhoneNumber]:
        items = [
            item
            for (item_tenant_id, _), item in self._items.items()
            if item_tenant_id == tenant_id
        ]
        items.sort(key=lambda item: item.created_at)
        return items

    async def get(
        self, phone_number_id: UUID, tenant_id: UUID
    ) -> PhoneNumber | None:
        return self._items.get((tenant_id, phone_number_id))

    async def get_by_e164(self, e164_number: str) -> PhoneNumber | None:
        return self._find_e164(e164_number)

    async def create(
        self, tenant_id: UUID, payload: PhoneNumberCreate
    ) -> PhoneNumber:
        if self._find_e164(payload.e164_number) is not None:
            raise PhoneNumberConflict()
        now = datetime.now(UTC)
        number = PhoneNumber(
            id=uuid4(),
            tenant_id=tenant_id,
            voice_agent_instance_id=payload.voice_agent_instance_id,
            e164_number=payload.e164_number,
            provider=payload.provider,
            inbound_trunk_id=payload.inbound_trunk_id,
            dispatch_rule_id=payload.dispatch_rule_id,
            enabled=payload.enabled,
            created_at=now,
            updated_at=now,
        )
        self._items[(tenant_id, number.id)] = number
        return number

    async def save(self, number: PhoneNumber) -> PhoneNumber:
        existing = self._find_e164(number.e164_number)
        if existing is not None and existing.id != number.id:
            raise PhoneNumberConflict()
        stored = number.model_copy(update={"updated_at": datetime.now(UTC)})
        self._items[(stored.tenant_id, stored.id)] = stored
        return stored

    async def delete(self, phone_number_id: UUID, tenant_id: UUID) -> bool:
        return self._items.pop((tenant_id, phone_number_id), None) is not None
