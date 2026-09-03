from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Response, status

from ..clock import NowProvider, utc_now
from ..dependencies import TenantId
from ..domain.appointment import (
    Appointment,
    AppointmentCreate,
    AppointmentPage,
    AppointmentUpdate,
)
from ..repositories.appointments import AppointmentRepository
from ..repositories.customer_services import CustomerServiceRepository
from ..repositories.scheduling import SchedulingRepository
from ..services.booking import SlotUnavailableError, ensure_slot_available


def create_router(
    appointments: AppointmentRepository,
    customer_services: CustomerServiceRepository,
    scheduling: SchedulingRepository,
    *,
    now_provider: NowProvider = utc_now,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/appointments")

    async def _resolve_instance(
        instance_id: UUID | None, tenant_id: UUID
    ) -> UUID | None:
        if instance_id is None:
            return None
        instance = await customer_services.get(instance_id, tenant_id)
        if instance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer service not found",
            )
        return instance_id

    @router.get("", response_model=AppointmentPage)
    async def list_appointments(
        tenant_id: TenantId,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        status_filter: str | None = Query(default=None, alias="status"),
        include_cancelled: bool = False,
    ) -> AppointmentPage:
        items, total = await appointments.list_for_tenant(
            tenant_id,
            limit=limit,
            offset=offset,
            status=status_filter,
            include_cancelled=include_cancelled,
        )
        return AppointmentPage(items=items, total=total)

    @router.post(
        "",
        response_model=Appointment,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_appointment(
        request: AppointmentCreate,
        tenant_id: TenantId,
    ) -> Appointment:
        instance_id = await _resolve_instance(
            request.voice_agent_instance_id, tenant_id
        )
        now = now_provider()
        try:
            await ensure_slot_available(
                appointments=appointments,
                scheduling=scheduling,
                tenant_id=tenant_id,
                instance_id=instance_id,
                slot_start=request.slot_start,
                slot_end=request.slot_end,
                service_offering_id=request.service_offering_id,
                now=now,
            )
        except SlotUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            ) from error
        return await appointments.create(
            Appointment(
                id=uuid4(),
                tenant_id=tenant_id,
                voice_agent_instance_id=instance_id,
                service_offering_id=request.service_offering_id,
                patient_name=request.patient_name,
                phone=request.phone,
                service=request.service,
                slot_start=request.slot_start,
                slot_end=request.slot_end,
                status=request.status,
                source="manual",
                notes=request.notes,
                created_at=now,
                updated_at=now,
            )
        )

    @router.get("/{appointment_id}", response_model=Appointment)
    async def get_appointment(
        appointment_id: UUID,
        tenant_id: TenantId,
    ) -> Appointment:
        item = await appointments.get(appointment_id, tenant_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found",
            )
        return item

    @router.patch("/{appointment_id}", response_model=Appointment)
    async def update_appointment(
        appointment_id: UUID,
        update: AppointmentUpdate,
        tenant_id: TenantId,
    ) -> Appointment:
        item = await appointments.get(appointment_id, tenant_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found",
            )
        if item.status == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="cancelled appointment cannot be modified",
            )
        data = update.model_dump(exclude_unset=True)
        slot_start = data.get("slot_start", item.slot_start)
        slot_end = data.get("slot_end", item.slot_end)
        if slot_end < slot_start:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="日期不可使用",
            )
        updated = item.model_copy(update=data)
        try:
            await ensure_slot_available(
                appointments=appointments,
                scheduling=scheduling,
                tenant_id=tenant_id,
                instance_id=updated.voice_agent_instance_id,
                slot_start=updated.slot_start,
                slot_end=updated.slot_end,
                service_offering_id=updated.service_offering_id,
                exclude_id=updated.id,
                now=now_provider(),
            )
        except SlotUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            ) from error
        return await appointments.save(updated)

    @router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def cancel_appointment(
        appointment_id: UUID,
        tenant_id: TenantId,
    ) -> Response:
        item = await appointments.get(appointment_id, tenant_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found",
            )
        if item.status != "cancelled":
            await appointments.save(
                item.model_copy(update={"status": "cancelled"})
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
