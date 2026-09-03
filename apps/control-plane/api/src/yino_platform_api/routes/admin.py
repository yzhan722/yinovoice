"""Platform-admin console endpoints: tenants and console user accounts."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from ..dependencies import PlatformAdmin
from ..domain.account import (
    AccountStatusUpdate,
    PasswordReset,
    TenantCreate,
    TenantPage,
    TenantView,
    UserAccount,
    UserAccountCreate,
    UserAccountPage,
)
from ..repositories.accounts import (
    AccountConflict,
    TenantConflict,
    TenantRepository,
    UserAccountRepository,
)
from ..services.passwords import hash_password


def create_router(
    tenants: TenantRepository,
    users: UserAccountRepository,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin")

    @router.get("/tenants", response_model=TenantPage)
    async def list_tenants(_: PlatformAdmin) -> TenantPage:
        items = await tenants.list()
        return TenantPage(items=items, total=len(items))

    @router.post(
        "/tenants", response_model=TenantView, status_code=status.HTTP_201_CREATED
    )
    async def create_tenant(payload: TenantCreate, _: PlatformAdmin) -> TenantView:
        try:
            return await tenants.create(payload)
        except TenantConflict as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="tenant already exists",
            ) from error

    @router.get("/users", response_model=UserAccountPage)
    async def list_users(
        _: PlatformAdmin, tenant_id: UUID | None = None
    ) -> UserAccountPage:
        items = await users.list(tenant_id)
        return UserAccountPage(items=items, total=len(items))

    @router.post(
        "/users", response_model=UserAccount, status_code=status.HTTP_201_CREATED
    )
    async def create_user(payload: UserAccountCreate, _: PlatformAdmin) -> UserAccount:
        if await tenants.get(payload.tenant_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="tenant not found",
            )
        try:
            return await users.create(payload, hash_password(payload.password))
        except AccountConflict as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="account already exists",
            ) from error

    @router.post("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
    async def reset_password(
        user_id: UUID, payload: PasswordReset, _: PlatformAdmin
    ) -> None:
        if not await users.set_password(user_id, hash_password(payload.password)):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="user not found"
            )

    @router.post("/users/{user_id}/status", response_model=UserAccount)
    async def update_status(
        user_id: UUID, payload: AccountStatusUpdate, admin: PlatformAdmin
    ) -> UserAccount:
        if admin.user_id == user_id and payload.status == "disabled":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="cannot disable the current account",
            )
        updated = await users.set_status(user_id, payload.status)
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="user not found"
            )
        return updated

    return router
