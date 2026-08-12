from typing import Annotated
from uuid import UUID

from fastapi import Header

TenantId = Annotated[UUID, Header(alias="X-Tenant-ID")]
