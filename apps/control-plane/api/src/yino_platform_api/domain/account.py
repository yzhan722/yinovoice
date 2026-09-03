"""Operator accounts and tenants for the multi-tenant console."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

Role = Literal["platform_admin", "tenant_operator"]
AccountStatus = Literal["active", "disabled"]
TenantStatus = Literal["active", "disabled"]


class UserAccount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    tenant_id: UUID
    account: str
    nickname: str
    role: Role
    status: AccountStatus
    created_at: datetime
    updated_at: datetime


class UserAccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    account: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=6, max_length=200)
    nickname: str = Field(default="", max_length=80)
    role: Role = "tenant_operator"

    @field_validator("account")
    @classmethod
    def _strip_account(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("account must not be blank")
        return stripped


class PasswordReset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=6, max_length=200)


class AccountStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: AccountStatus


class UserAccountPage(BaseModel):
    items: list[UserAccount]
    total: int = Field(ge=0)


class TenantView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str
    home_region: str
    status: TenantStatus
    created_at: datetime


class TenantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None
    name: str = Field(min_length=1, max_length=120)
    home_region: str = Field(default="cn-mainland", max_length=40)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped


class TenantPage(BaseModel):
    items: list[TenantView]
    total: int = Field(ge=0)
