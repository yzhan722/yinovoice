from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Response, status

from ..dependencies import TenantId
from ..domain.phone_number import (
    PhoneNumber,
    PhoneNumberCreate,
    PhoneNumberPage,
    PhoneNumberUpdate,
    PhoneNumberView,
    normalize_e164,
)
from ..repositories.customer_services import CustomerServiceRepository
from ..repositories.phone_numbers import PhoneNumberConflict, PhoneNumberRepository
from ..services.phone_lookup_auth import (
    PHONE_LOOKUP_HEADER,
    phone_lookup_token_matches,
)


def create_router(
    phone_numbers: PhoneNumberRepository,
    customer_services: CustomerServiceRepository,
    *,
    lookup_token: str | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/phone-numbers")

    async def _config_version(tenant_id: UUID, instance_id: UUID) -> int:
        instance = await customer_services.get(instance_id, tenant_id)
        if instance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer service not found",
            )
        return instance.version

    async def _view(number: PhoneNumber) -> PhoneNumberView:
        return PhoneNumberView(
            **number.model_dump(),
            config_version=await _config_version(
                number.tenant_id, number.voice_agent_instance_id
            ),
        )

    @router.get("", response_model=PhoneNumberPage)
    async def list_phone_numbers(tenant_id: TenantId) -> PhoneNumberPage:
        items = await phone_numbers.list_for_tenant(tenant_id)
        views = [await _view(item) for item in items]
        return PhoneNumberPage(items=views, total=len(views))

    @router.get("/lookup", response_model=PhoneNumberView)
    async def lookup_phone_number(
        number: str = Query(min_length=3, max_length=32),
        x_phone_lookup_token: Annotated[
            str | None,
            Header(alias=PHONE_LOOKUP_HEADER),
        ] = None,
    ) -> PhoneNumberView:
        if not phone_lookup_token_matches(lookup_token, x_phone_lookup_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
            )
        try:
            e164 = normalize_e164(number)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(error),
            ) from error
        item = await phone_numbers.get_by_e164(e164)
        if item is None or not item.enabled:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Phone number not found",
            )
        try:
            return await _view(item)
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Phone number not found",
            ) from None

    @router.post(
        "",
        response_model=PhoneNumberView,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_phone_number(
        payload: PhoneNumberCreate,
        tenant_id: TenantId,
    ) -> PhoneNumberView:
        await _config_version(tenant_id, payload.voice_agent_instance_id)
        try:
            created = await phone_numbers.create(tenant_id, payload)
        except PhoneNumberConflict as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number already mapped",
            ) from error
        return await _view(created)

    @router.get("/{phone_number_id}", response_model=PhoneNumberView)
    async def get_phone_number(
        phone_number_id: UUID,
        tenant_id: TenantId,
    ) -> PhoneNumberView:
        item = await phone_numbers.get(phone_number_id, tenant_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Phone number not found",
            )
        return await _view(item)

    @router.put("/{phone_number_id}", response_model=PhoneNumberView)
    async def update_phone_number(
        phone_number_id: UUID,
        update: PhoneNumberUpdate,
        tenant_id: TenantId,
    ) -> PhoneNumberView:
        item = await phone_numbers.get(phone_number_id, tenant_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Phone number not found",
            )
        data = update.model_dump(exclude_unset=True)
        instance_id = data.get("voice_agent_instance_id", item.voice_agent_instance_id)
        await _config_version(tenant_id, instance_id)
        try:
            saved = await phone_numbers.save(item.model_copy(update=data))
        except PhoneNumberConflict as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number already mapped",
            ) from error
        return await _view(saved)

    @router.delete("/{phone_number_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_phone_number(
        phone_number_id: UUID,
        tenant_id: TenantId,
    ) -> Response:
        deleted = await phone_numbers.delete(phone_number_id, tenant_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Phone number not found",
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
