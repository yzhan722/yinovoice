from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from ..domain.scheduling import (
    BusinessHours,
    BusinessHoursWrite,
    ScheduleException,
    ScheduleExceptionCreate,
    SchedulingProfile,
    SchedulingProfileUpdate,
    ServiceOffering,
    ServiceOfferingCreate,
)


class SchedulingRepository(Protocol):
    async def list_offerings(
        self, tenant_id: UUID, instance_id: UUID
    ) -> list[ServiceOffering]: ...

    async def get_offering(
        self, offering_id: UUID, tenant_id: UUID
    ) -> ServiceOffering | None: ...

    async def find_offering_by_name(
        self, tenant_id: UUID, instance_id: UUID, name: str
    ) -> ServiceOffering | None: ...

    async def create_offering(self, offering: ServiceOffering) -> ServiceOffering: ...

    async def save_offering(self, offering: ServiceOffering) -> ServiceOffering: ...

    async def get_profile(
        self, tenant_id: UUID, instance_id: UUID
    ) -> SchedulingProfile | None: ...

    async def upsert_profile(
        self, profile: SchedulingProfile
    ) -> SchedulingProfile: ...

    async def list_hours(
        self, tenant_id: UUID, instance_id: UUID
    ) -> list[BusinessHours]: ...

    async def replace_hours(
        self,
        tenant_id: UUID,
        instance_id: UUID,
        hours: list[BusinessHours],
    ) -> list[BusinessHours]: ...

    async def list_exceptions(
        self, tenant_id: UUID, instance_id: UUID
    ) -> list[ScheduleException]: ...

    async def create_exception(
        self, item: ScheduleException
    ) -> ScheduleException: ...

    async def delete_exception(
        self, exception_id: UUID, tenant_id: UUID
    ) -> bool: ...


class InMemorySchedulingRepository:
    def __init__(self) -> None:
        self._offerings: dict[tuple[UUID, UUID], ServiceOffering] = {}
        self._profiles: dict[tuple[UUID, UUID], SchedulingProfile] = {}
        self._hours: dict[tuple[UUID, UUID], list[BusinessHours]] = {}
        self._exceptions: dict[tuple[UUID, UUID], ScheduleException] = {}

    async def list_offerings(
        self, tenant_id: UUID, instance_id: UUID
    ) -> list[ServiceOffering]:
        return [
            item.model_copy(deep=True)
            for item in self._offerings.values()
            if item.tenant_id == tenant_id
            and item.voice_agent_instance_id == instance_id
        ]

    async def get_offering(
        self, offering_id: UUID, tenant_id: UUID
    ) -> ServiceOffering | None:
        item = self._offerings.get((tenant_id, offering_id))
        return item.model_copy(deep=True) if item is not None else None

    async def find_offering_by_name(
        self, tenant_id: UUID, instance_id: UUID, name: str
    ) -> ServiceOffering | None:
        matches = [
            item
            for item in self._offerings.values()
            if item.tenant_id == tenant_id
            and item.voice_agent_instance_id == instance_id
            and item.enabled
            and item.name == name
        ]
        if len(matches) != 1:
            return None
        return matches[0].model_copy(deep=True)

    async def create_offering(self, offering: ServiceOffering) -> ServiceOffering:
        stored = offering.model_copy(deep=True)
        self._offerings[(stored.tenant_id, stored.id)] = stored
        return stored.model_copy(deep=True)

    async def save_offering(self, offering: ServiceOffering) -> ServiceOffering:
        stored = offering.model_copy(
            update={"updated_at": datetime.now(UTC)},
            deep=True,
        )
        self._offerings[(stored.tenant_id, stored.id)] = stored
        return stored.model_copy(deep=True)

    async def get_profile(
        self, tenant_id: UUID, instance_id: UUID
    ) -> SchedulingProfile | None:
        item = self._profiles.get((tenant_id, instance_id))
        return item.model_copy(deep=True) if item is not None else None

    async def upsert_profile(self, profile: SchedulingProfile) -> SchedulingProfile:
        stored = profile.model_copy(
            update={"updated_at": datetime.now(UTC)},
            deep=True,
        )
        self._profiles[(stored.tenant_id, stored.voice_agent_instance_id)] = stored
        return stored.model_copy(deep=True)

    async def list_hours(
        self, tenant_id: UUID, instance_id: UUID
    ) -> list[BusinessHours]:
        return [
            item.model_copy(deep=True)
            for item in self._hours.get((tenant_id, instance_id), [])
        ]

    async def replace_hours(
        self,
        tenant_id: UUID,
        instance_id: UUID,
        hours: list[BusinessHours],
    ) -> list[BusinessHours]:
        stored = [item.model_copy(deep=True) for item in hours]
        self._hours[(tenant_id, instance_id)] = stored
        return [item.model_copy(deep=True) for item in stored]

    async def list_exceptions(
        self, tenant_id: UUID, instance_id: UUID
    ) -> list[ScheduleException]:
        return [
            item.model_copy(deep=True)
            for item in self._exceptions.values()
            if item.tenant_id == tenant_id
            and item.voice_agent_instance_id == instance_id
        ]

    async def create_exception(self, item: ScheduleException) -> ScheduleException:
        stored = item.model_copy(deep=True)
        self._exceptions[(stored.tenant_id, stored.id)] = stored
        return stored.model_copy(deep=True)

    async def delete_exception(self, exception_id: UUID, tenant_id: UUID) -> bool:
        return self._exceptions.pop((tenant_id, exception_id), None) is not None


def new_offering(
    tenant_id: UUID, payload: ServiceOfferingCreate
) -> ServiceOffering:
    stamp = datetime.now(UTC)
    return ServiceOffering(
        id=uuid4(),
        tenant_id=tenant_id,
        created_at=stamp,
        updated_at=stamp,
        **payload.model_dump(),
    )


def profile_from_update(
    tenant_id: UUID,
    instance_id: UUID,
    payload: SchedulingProfileUpdate,
) -> SchedulingProfile:
    return SchedulingProfile(
        tenant_id=tenant_id,
        voice_agent_instance_id=instance_id,
        updated_at=datetime.now(UTC),
        **payload.model_dump(),
    )


def hours_from_writes(
    tenant_id: UUID,
    instance_id: UUID,
    payloads: list[BusinessHoursWrite],
) -> list[BusinessHours]:
    return [
        BusinessHours(
            id=uuid4(),
            tenant_id=tenant_id,
            voice_agent_instance_id=instance_id,
            **item.model_dump(),
        )
        for item in payloads
    ]


def exception_from_create(
    tenant_id: UUID, payload: ScheduleExceptionCreate
) -> ScheduleException:
    return ScheduleException(
        id=uuid4(),
        tenant_id=tenant_id,
        **payload.model_dump(),
    )
