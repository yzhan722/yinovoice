from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from uuid import UUID

from ..domain.customer_service import DEMO_TENANT_ID


class InvalidAuthToken(ValueError):
    """Raised when a bearer token is missing, expired, or forged."""


@dataclass(frozen=True)
class AuthPrincipal:
    tenant_id: UUID
    account: str
    nickname: str


class AuthService:
    def __init__(
        self,
        *,
        secret: str,
        account: str,
        password: str,
        tenant_id: UUID,
        nickname: str = "租户操作员",
        ttl_seconds: int = 86_400,
    ) -> None:
        self._secret = (secret or "yino-demo-auth").encode("utf-8")
        self._account = account.strip()
        self._password = password
        self._tenant_id = tenant_id
        self._nickname = nickname
        self._ttl_seconds = ttl_seconds

    def login(
        self, account: str, password: str
    ) -> tuple[str, int, AuthPrincipal] | None:
        if not hmac.compare_digest(account.strip(), self._account):
            return None
        if not hmac.compare_digest(password, self._password):
            return None
        exp = int(time.time()) + self._ttl_seconds
        principal = AuthPrincipal(
            tenant_id=self._tenant_id,
            account=self._account,
            nickname=self._nickname,
        )
        return self.issue_token(principal, exp=exp), exp * 1000, principal

    def issue_token(self, principal: AuthPrincipal, *, exp: int) -> str:
        payload = json.dumps(
            {
                "tid": str(principal.tenant_id),
                "acc": principal.account,
                "exp": exp,
            },
            separators=(",", ":"),
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
        expected = hmac.new(
            self._secret, body.encode("ascii"), hashlib.sha256
        ).digest()
        given = _b64decode(signature)
        if not hmac.compare_digest(expected, given):
            raise InvalidAuthToken("bad signature")
        payload = json.loads(_b64decode(body).decode("utf-8"))
        exp = int(payload["exp"])
        if exp < int(time.time()):
            raise InvalidAuthToken("expired")
        return AuthPrincipal(
            tenant_id=UUID(str(payload["tid"])),
            account=str(payload["acc"]),
            nickname=self._nickname,
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
