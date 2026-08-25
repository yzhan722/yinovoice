from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status

from .services.auth import AuthService, InvalidAuthToken

_auth_service: AuthService | None = None


def bind_auth_service(service: AuthService) -> None:
    global _auth_service
    _auth_service = service


async def resolve_tenant_id(
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> UUID:
    token_tenant: UUID | None = None
    if (
        authorization
        and authorization.lower().startswith("bearer ")
        and _auth_service is not None
    ):
        raw = authorization.split(" ", 1)[1].strip()
        try:
            token_tenant = _auth_service.verify_token(raw).tenant_id
        except InvalidAuthToken as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid token",
            ) from error
    if (
        token_tenant is not None
        and x_tenant_id is not None
        and token_tenant != x_tenant_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="tenant mismatch",
        )
    if token_tenant is not None:
        return token_tenant
    if x_tenant_id is not None:
        return x_tenant_id
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="missing tenant",
    )


TenantId = Annotated[UUID, Depends(resolve_tenant_id)]
