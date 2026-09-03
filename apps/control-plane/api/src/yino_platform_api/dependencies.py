from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status

from .services.auth import AuthPrincipal, AuthService, InvalidAuthToken

_auth_service: AuthService | None = None


def bind_auth_service(service: AuthService) -> None:
    global _auth_service
    _auth_service = service


def _principal_from_header(authorization: str | None) -> AuthPrincipal | None:
    if not (
        authorization
        and authorization.lower().startswith("bearer ")
        and _auth_service is not None
    ):
        return None
    raw = authorization.split(" ", 1)[1].strip()
    try:
        return _auth_service.verify_token(raw)
    except InvalidAuthToken as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token",
        ) from error


async def resolve_tenant_id(
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> UUID:
    principal = _principal_from_header(authorization)
    if principal is not None:
        # Platform admins may act on behalf of any tenant by naming it in the
        # header; tenant operators are pinned to the tenant in their token.
        if x_tenant_id is not None and x_tenant_id != principal.tenant_id:
            if principal.is_platform_admin:
                return x_tenant_id
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="tenant mismatch",
            )
        return principal.tenant_id
    if x_tenant_id is not None:
        return x_tenant_id
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="missing tenant",
    )


async def require_principal(
    authorization: Annotated[str | None, Header()] = None,
) -> AuthPrincipal:
    principal = _principal_from_header(authorization)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing token",
        )
    return principal


async def require_platform_admin(
    principal: Annotated[AuthPrincipal, Depends(require_principal)],
) -> AuthPrincipal:
    if not principal.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="platform admin required",
        )
    return principal


TenantId = Annotated[UUID, Depends(resolve_tenant_id)]
Principal = Annotated[AuthPrincipal, Depends(require_principal)]
PlatformAdmin = Annotated[AuthPrincipal, Depends(require_platform_admin)]
