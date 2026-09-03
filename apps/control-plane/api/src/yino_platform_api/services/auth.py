from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import time
from contextlib import suppress
from dataclasses import dataclass
from uuid import UUID

from ..domain.account import Role, UserAccountCreate
from ..domain.customer_service import DEMO_TENANT_ID
from ..repositories.accounts import (
    AccountConflict,
    InMemoryUserAccountRepository,
    UserAccountRepository,
)
from .passwords import hash_password, verify_password


class InvalidAuthToken(ValueError):
    """Raised when a bearer token is missing, expired, or forged."""


@dataclass(frozen=True)
class AuthPrincipal:
    tenant_id: UUID
    account: str
    nickname: str
    role: Role = "tenant_operator"
    user_id: UUID | None = None

    @property
    def is_platform_admin(self) -> bool:
        return self.role == "platform_admin"


class AuthService:
    """HMAC bearer tokens backed by a user-account repository.

    The configured demo operator (and optional platform admin) are seeded into
    an empty repository on first use so fresh deployments and tests keep the
    historical ``demo / demo123`` behaviour.
    """

    def __init__(
        self,
        *,
        secret: str,
        account: str,
        password: str,
        tenant_id: UUID,
        nickname: str = "租户操作员",
        ttl_seconds: int = 86_400,
        users: UserAccountRepository | None = None,
        admin_account: str | None = None,
        admin_password: str | None = None,
    ) -> None:
        self._secret = (secret or "yino-demo-auth").encode("utf-8")
        self._bootstrap_account = account.strip()
        self._bootstrap_password = password
        self._bootstrap_tenant_id = tenant_id
        self._bootstrap_nickname = nickname
        self._admin_account = (admin_account or "").strip() or None
        self._admin_password = admin_password
        self._ttl_seconds = ttl_seconds
        self._users = users if users is not None else InMemoryUserAccountRepository()
        self._bootstrap_lock = asyncio.Lock()
        self._bootstrapped = False

    @property
    def users(self) -> UserAccountRepository:
        return self._users

    async def ensure_bootstrap(self) -> None:
        if self._bootstrapped:
            return
        async with self._bootstrap_lock:
            if self._bootstrapped:
                return
            if await self._users.count() == 0:
                await self._seed(
                    self._bootstrap_account,
                    self._bootstrap_password,
                    self._bootstrap_nickname,
                    "tenant_operator",
                )
                if self._admin_account and self._admin_password:
                    await self._seed(
                        self._admin_account,
                        self._admin_password,
                        "平台管理员",
                        "platform_admin",
                    )
            self._bootstrapped = True

    async def _seed(
        self, account: str, password: str, nickname: str, role: Role
    ) -> None:
        with suppress(AccountConflict):
            await self._users.create(
                UserAccountCreate(
                    tenant_id=self._bootstrap_tenant_id,
                    account=account,
                    password=password,
                    nickname=nickname,
                    role=role,
                ),
                hash_password(password),
            )

    async def login(
        self, account: str, password: str
    ) -> tuple[str, int, AuthPrincipal] | None:
        await self.ensure_bootstrap()
        found = await self._users.get_by_account(account)
        if found is None:
            # Burn comparable time so account enumeration is not trivial.
            verify_password(password, hash_password("x"))
            return None
        user, password_hash = found
        if not verify_password(password, password_hash):
            return None
        if user.status != "active":
            return None
        exp = int(time.time()) + self._ttl_seconds
        principal = AuthPrincipal(
            tenant_id=user.tenant_id,
            account=user.account,
            nickname=user.nickname,
            role=user.role,
            user_id=user.id,
        )
        return self.issue_token(principal, exp=exp), exp * 1000, principal

    def issue_token(self, principal: AuthPrincipal, *, exp: int) -> str:
        payload = json.dumps(
            {
                "tid": str(principal.tenant_id),
                "acc": principal.account,
                "nick": principal.nickname,
                "role": principal.role,
                "uid": str(principal.user_id) if principal.user_id else None,
                "exp": exp,
            },
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        body = base64.urlsafe_b64encode(payload).rstrip(b"=")
        sig = hmac.new(self._secret, body, hashlib.sha256).digest()
        return (
            body.decode("ascii")
            + "."
            + base64.urlsafe_b64encode(sig).rstrip(b"=").decode("ascii")
        )

    def verify_token(self, token: str) -> AuthPrincipal:
        try:
            body, signature = token.split(".", 1)
        except ValueError as error:
            raise InvalidAuthToken("malformed token") from error
        expected = hmac.new(self._secret, body.encode("ascii"), hashlib.sha256).digest()
        try:
            given = _b64decode(signature)
        except ValueError as error:
            raise InvalidAuthToken("bad signature") from error
        if not hmac.compare_digest(expected, given):
            raise InvalidAuthToken("bad signature")
        payload = json.loads(_b64decode(body).decode("utf-8"))
        exp = int(payload["exp"])
        if exp < int(time.time()):
            raise InvalidAuthToken("expired")
        role = payload.get("role") or "tenant_operator"
        if role not in ("platform_admin", "tenant_operator"):
            raise InvalidAuthToken("unknown role")
        raw_uid = payload.get("uid")
        return AuthPrincipal(
            tenant_id=UUID(str(payload["tid"])),
            account=str(payload["acc"]),
            nickname=str(payload.get("nick") or self._bootstrap_nickname),
            role=role,
            user_id=UUID(str(raw_uid)) if raw_uid else None,
        )


def default_auth_service(
    *,
    secret: str,
    account: str,
    password: str,
    tenant_id: UUID | None,
) -> AuthService:
    return AuthService(
        secret=secret,
        account=account or "demo",
        password=password or "demo123",
        tenant_id=tenant_id or DEMO_TENANT_ID,
    )


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
