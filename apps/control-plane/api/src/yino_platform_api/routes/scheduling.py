from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from ..clock import NowProvider, utc_now
from ..dependencies import TenantId
from ..domain.scheduling import (
    AvailabilityPage,
    BusinessHours,
    BusinessHoursWrite,
    ScheduleException,
    ScheduleExceptionCreate,
    SchedulingProfile,
    SchedulingProfileUpdate,
    ServiceOffering,
    ServiceOfferingCreate,
    ServiceOfferingUpdate,
)
from ..repositories.appointments import AppointmentRepository
from ..repositories.customer_services import CustomerServiceRepository
from ..repositories.scheduling import (
    SchedulingRepository,
    exception_from_create,
    hours_from_writes,
    new_offering,
    profile_from_update,
)
from ..services.availability import generate_available_slots, occupying_ranges


def create_router(
    scheduling: SchedulingRepository,
    customer_services: CustomerServiceRepository,
    appointments: AppointmentRepository,
    *,
    now_provider: NowProvider = utc_now,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    async def _require_instance(instance_id: UUID, tenant_id: UUID) -> None:
        instance = await customer_services.get(instance_id, tenant_id)
        if instance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer service not found",
            )

    @router.get("/service-offerings", response_model=list[ServiceOffering])
    async def list_offerings(
        tenant_id: TenantId,
        voice_agent_instance_id: UUID,
    ) -> list[ServiceOffering]:
        await _require_instance(voice_agent_instance_id, tenant_id)
        return await scheduling.list_offerings(tenant_id, voice_agent_instance_id)

    @router.post(
        "/service-offerings",
        response_model=ServiceOffering,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_offering(
        payload: ServiceOfferingCreate,
        tenant_id: TenantId,
    ) -> ServiceOffering:
        await _require_instance(payload.voice_agent_instance_id, tenant_id)
        return await scheduling.create_offering(new_offering(tenant_id, payload))

    @router.put("/service-offerings/{offering_id}", response_model=ServiceOffering)
    async def update_offering(
        offering_id: UUID,
        payload: ServiceOfferingUpdate,
        tenant_id: TenantId,
    ) -> ServiceOffering:
        existing = await scheduling.get_offering(offering_id, tenant_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service offering not found",
            )
        updated = existing.model_copy(
            update=payload.model_dump(exclude_unset=True)
        )
        return await scheduling.save_offering(updated)

    @router.get(
        "/scheduling-profiles/{instance_id}",
        response_model=SchedulingProfile,
    )
    async def get_profile(
        instance_id: UUID,
        tenant_id: TenantId,
    ) -> SchedulingProfile:
        await _require_instance(instance_id, tenant_id)
        profile = await scheduling.get_profile(tenant_id, instance_id)
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scheduling profile not found",
            )
        return profile

    @router.put(
        "/scheduling-profiles/{instance_id}",
        response_model=SchedulingProfile,
    )
    async def put_profile(
        instance_id: UUID,
        payload: SchedulingProfileUpdate,
        tenant_id: TenantId,
    ) -> SchedulingProfile:
        await _require_instance(instance_id, tenant_id)
        return await scheduling.upsert_profile(
            profile_from_update(tenant_id, instance_id, payload)
        )

    @router.get("/business-hours", response_model=list[BusinessHours])
    async def list_hours(
        tenant_id: TenantId,
        voice_agent_instance_id: UUID,
    ) -> list[BusinessHours]:
        await _require_instance(voice_agent_instance_id, tenant_id)
        return await scheduling.list_hours(tenant_id, voice_agent_instance_id)

    @router.put("/business-hours", response_model=list[BusinessHours])
    async def put_hours(
        tenant_id: TenantId,
        voice_agent_instance_id: UUID,
        payload: list[BusinessHoursWrite],
    ) -> list[BusinessHours]:
        await _require_instance(voice_agent_instance_id, tenant_id)
        return await scheduling.replace_hours(
            tenant_id,
            voice_agent_instance_id,
            hours_from_writes(tenant_id, voice_agent_instance_id, payload),
        )

    @router.get("/schedule-exceptions", response_model=list[ScheduleException])
    async def list_exceptions(
        tenant_id: TenantId,
        voice_agent_instance_id: UUID,
    ) -> list[ScheduleException]:
        await _require_instance(voice_agent_instance_id, tenant_id)
        return await scheduling.list_exceptions(tenant_id, voice_agent_instance_id)

    @router.post(
        "/schedule-exceptions",
        response_model=ScheduleException,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_exception(
        payload: ScheduleExceptionCreate,
        tenant_id: TenantId,
    ) -> ScheduleException:
        await _require_instance(payload.voice_agent_instance_id, tenant_id)
        return await scheduling.create_exception(
            exception_from_create(tenant_id, payload)
        )

    @router.delete(
        "/schedule-exceptions/{exception_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def delete_exception(
        exception_id: UUID,
        tenant_id: TenantId,
    ) -> Response:
        deleted = await scheduling.delete_exception(exception_id, tenant_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schedule exception not found",
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get("/availability", response_model=AvailabilityPage)
    async def list_availability(
        tenant_id: TenantId,
        voice_agent_instance_id: UUID,
        service_offering_id: UUID,
        date_from: date,
        date_to: date,
    ) -> AvailabilityPage:
        await _require_instance(voice_agent_instance_id, tenant_id)
        offering = await scheduling.get_offering(service_offering_id, tenant_id)
        if (
            offering is None
            or offering.voice_agent_instance_id != voice_agent_instance_id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service offering not found",
            )
        profile = await scheduling.get_profile(tenant_id, voice_agent_instance_id)
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scheduling profile not found",
            )
        if date_to < date_from:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="date_to must be on or after date_from",
            )
        occupying = occupying_ranges(
            await appointments.list_occupying(
                tenant_id,
                voice_agent_instance_id,
            )
        )
        items = generate_available_slots(
            profile=profile,
            offering=offering,
            hours=await scheduling.list_hours(tenant_id, voice_agent_instance_id),
            exceptions=await scheduling.list_exceptions(
                tenant_id, voice_agent_instance_id
            ),
            occupying=occupying,
            date_from=date_from,
            date_to=date_to,
            now=now_provider(),
        )
        return AvailabilityPage(items=items, total=len(items))

    return router
