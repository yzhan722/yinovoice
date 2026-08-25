"""PostgreSQL adapter for CustomerServiceRepository."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...db.models import VoiceAgentInstance
from ...db.seed import DEMO_TEMPLATE_VERSION_ID
from ...domain.customer_service import (
    CustomerServiceInstance,
    ResponseProfile,
    VoiceProfile,
)
from ..customer_services import (
    CustomerServiceAlreadyExists,
    CustomerServiceVersionConflict,
)


def _to_domain(row: VoiceAgentInstance) -> CustomerServiceInstance:
    return CustomerServiceInstance(
        id=row.id,
        tenant_id=row.tenant_id,
        version=row.version,
        display_name=row.display_name,
        organization_name=row.organization_name,
        business_profile=row.business_profile,
        primary_language=row.primary_language,
        greeting=row.greeting,
        platform_prompt=row.platform_prompt,
        tenant_prompt=row.tenant_prompt,
        voice=VoiceProfile.model_validate(row.voice_config),
        response=ResponseProfile.model_validate(row.response_config),
        insights_profile=row.insights_profile,
        deleted_at=row.deleted_at,
    )


class PostgresCustomerServiceRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get_including_deleted(
        self, instance_id: UUID, tenant_id: UUID
    ) -> CustomerServiceInstance | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(VoiceAgentInstance).where(
                    VoiceAgentInstance.tenant_id == tenant_id,
                    VoiceAgentInstance.id == instance_id,
                )
            )
            if row is None:
                return None
            return _to_domain(row)

    async def get(
        self, instance_id: UUID, tenant_id: UUID
    ) -> CustomerServiceInstance | None:
        instance = await self.get_including_deleted(instance_id, tenant_id)
        if instance is None or instance.deleted_at is not None:
            return None
        return instance

    async def list_for_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        offset: int,
        include_deleted: bool = False,
    ) -> tuple[list[CustomerServiceInstance], int]:
        async with self._sessions() as session:
            filters = [VoiceAgentInstance.tenant_id == tenant_id]
            if not include_deleted:
                filters.append(VoiceAgentInstance.deleted_at.is_(None))
            total = await session.scalar(
                select(func.count())
                .select_from(VoiceAgentInstance)
                .where(*filters)
            )
            rows = (
                await session.scalars(
                    select(VoiceAgentInstance)
                    .where(*filters)
                    .order_by(
                        VoiceAgentInstance.updated_at.desc(),
                        VoiceAgentInstance.id.desc(),
                    )
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
            return [_to_domain(row) for row in rows], int(total or 0)

    async def save(
        self, instance: CustomerServiceInstance
    ) -> CustomerServiceInstance:
        async with self._sessions() as session:
            if instance.version < 1:
                raise CustomerServiceVersionConflict()

            result = await session.execute(
                update(VoiceAgentInstance)
                .where(
                    VoiceAgentInstance.tenant_id == instance.tenant_id,
                    VoiceAgentInstance.id == instance.id,
                    VoiceAgentInstance.version == instance.version - 1,
                )
                .values(
                    version=instance.version,
                    display_name=instance.display_name,
                    organization_name=instance.organization_name,
                    business_profile=instance.business_profile,
                    primary_language=instance.primary_language,
                    greeting=instance.greeting,
                    platform_prompt=instance.platform_prompt,
                    tenant_prompt=instance.tenant_prompt,
                    voice_config=instance.voice.model_dump(mode="json"),
                    response_config=instance.response.model_dump(mode="json"),
                    insights_profile=instance.insights_profile,
                    deleted_at=instance.deleted_at,
                    updated_at=datetime.now(UTC),
                )
                .returning(VoiceAgentInstance)
            )
            updated = result.scalar_one_or_none()
            if updated is not None:
                await session.commit()
                return _to_domain(updated)

            existing = await session.scalar(
                select(VoiceAgentInstance).where(
                    VoiceAgentInstance.tenant_id == instance.tenant_id,
                    VoiceAgentInstance.id == instance.id,
                )
            )
            if existing is not None:
                raise CustomerServiceVersionConflict()

            session.add(
                VoiceAgentInstance(
                    id=instance.id,
                    tenant_id=instance.tenant_id,
                    template_version_id=DEMO_TEMPLATE_VERSION_ID,
                    version=instance.version,
                    display_name=instance.display_name,
                    organization_name=instance.organization_name,
                    business_profile=instance.business_profile,
                    primary_language=instance.primary_language,
                    greeting=instance.greeting,
                    platform_prompt=instance.platform_prompt,
                    tenant_prompt=instance.tenant_prompt,
                    voice_config=instance.voice.model_dump(mode="json"),
                    response_config=instance.response.model_dump(mode="json"),
                    insights_profile=instance.insights_profile,
                    deleted_at=instance.deleted_at,
                )
            )
            await session.commit()
            return instance

    async def create(
        self, instance: CustomerServiceInstance
    ) -> CustomerServiceInstance:
        async with self._sessions() as session:
            session.add(
                VoiceAgentInstance(
                    id=instance.id,
                    tenant_id=instance.tenant_id,
                    template_version_id=DEMO_TEMPLATE_VERSION_ID,
                    version=instance.version,
                    display_name=instance.display_name,
                    organization_name=instance.organization_name,
                    business_profile=instance.business_profile,
                    primary_language=instance.primary_language,
                    greeting=instance.greeting,
                    platform_prompt=instance.platform_prompt,
                    tenant_prompt=instance.tenant_prompt,
                    voice_config=instance.voice.model_dump(mode="json"),
                    response_config=instance.response.model_dump(mode="json"),
                    insights_profile=instance.insights_profile,
                    deleted_at=instance.deleted_at,
                )
            )
            try:
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise CustomerServiceAlreadyExists() from error
            return instance

    async def soft_delete(
        self, instance_id: UUID, tenant_id: UUID
    ) -> CustomerServiceInstance | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(VoiceAgentInstance).where(
                    VoiceAgentInstance.tenant_id == tenant_id,
                    VoiceAgentInstance.id == instance_id,
                )
            )
            if row is None:
                return None
            if row.deleted_at is None:
                row.deleted_at = datetime.now(UTC)
                row.updated_at = datetime.now(UTC)
                await session.commit()
                await session.refresh(row)
            return _to_domain(row)

    async def restore(
        self, instance_id: UUID, tenant_id: UUID
    ) -> CustomerServiceInstance | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(VoiceAgentInstance).where(
                    VoiceAgentInstance.tenant_id == tenant_id,
                    VoiceAgentInstance.id == instance_id,
                )
            )
            if row is None:
                return None
            if row.deleted_at is not None:
                row.deleted_at = None
                row.updated_at = datetime.now(UTC)
                await session.commit()
                await session.refresh(row)
            return _to_domain(row)

    async def hard_delete(
        self, instance_id: UUID, tenant_id: UUID
    ) -> CustomerServiceInstance | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(VoiceAgentInstance).where(
                    VoiceAgentInstance.tenant_id == tenant_id,
                    VoiceAgentInstance.id == instance_id,
                )
            )
            if row is None:
                return None
            instance = _to_domain(row)
            await session.execute(
                delete(VoiceAgentInstance).where(
                    VoiceAgentInstance.tenant_id == tenant_id,
                    VoiceAgentInstance.id == instance_id,
                )
            )
            await session.commit()
            return instance
