from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from ..services.auth import AuthService, InvalidAuthToken


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class LoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    tokenExpireTime: int
    account: str
    userAccount: str
    userNickname: str
    tenant_id: UUID


class MeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account: str
    userAccount: str
    userNickname: str
    tenant_id: UUID
    roles: list[str]


def create_router(auth: AuthService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/auth")

    @router.post("/login", response_model=LoginResponse)
    async def login(payload: LoginRequest) -> LoginResponse:
        result = await auth.login(payload.account, payload.password)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid credentials",
            )
        token, expire_ms, principal = result
        return LoginResponse(
            token=token,
            tokenExpireTime=expire_ms,
            account=principal.account,
            userAccount=principal.account,
            userNickname=principal.nickname,
            tenant_id=principal.tenant_id,
        )

    @router.get("/me", response_model=MeResponse)
    async def me(
        authorization: str | None = Header(default=None),
    ) -> MeResponse:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="missing token",
            )
        raw = authorization.split(" ", 1)[1].strip()
        try:
            principal = auth.verify_token(raw)
        except InvalidAuthToken as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid token",
            ) from error
        return MeResponse(
            account=principal.account,
            userAccount=principal.account,
            userNickname=principal.nickname,
            tenant_id=principal.tenant_id,
            roles=[principal.role],
        )

    return router
