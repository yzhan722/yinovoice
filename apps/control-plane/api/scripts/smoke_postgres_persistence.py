"""Local smoke: write via one app lifespan, verify via a second app lifespan."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://yino:yino@127.0.0.1:5432/yino_platform",
)

from yino_platform_api.app import create_app  # noqa: E402
from yino_platform_api.domain.customer_service import (  # noqa: E402
    DEMO_CUSTOMER_SERVICE_ID,
    DEMO_TENANT_ID,
)

TENANT = str(DEMO_TENANT_ID)
CS = str(DEMO_CUSTOMER_SERVICE_ID)


async def write_phase(marker: str) -> tuple[int, str, str]:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            response = await client.get(
                f"/api/v1/customer-services/{CS}",
                headers={"X-Tenant-ID": TENANT},
            )
            response.raise_for_status()
            body = response.json()
            expected = body["version"]
            body["expected_version"] = expected
            for key in (
                "id",
                "tenant_id",
                "business_profile",
                "primary_language",
                "version",
            ):
                body.pop(key, None)
            body["display_name"] = f"冒烟客服 {marker}"
            put = await client.put(
                f"/api/v1/customer-services/{CS}",
                headers={"X-Tenant-ID": TENANT},
                json=body,
            )
            put.raise_for_status()
            put_body = put.json()
            assert put_body["display_name"] == body["display_name"]
            assert put_body["version"] == expected + 1

            started = datetime(2026, 8, 11, 14, 0, tzinfo=UTC)
            created = await client.post(
                "/api/v1/call-records",
                headers={"X-Tenant-ID": TENANT},
                json={
                    "customer_service_id": CS,
                    "room_name": f"room-{marker}",
                    "status": "completed",
                    "started_at": started.isoformat().replace("+00:00", "Z"),
                    "ended_at": (started + timedelta(seconds=12))
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "duration_sec": 12,
                    "direction": "web",
                    "messages": [
                        {
                            "role": "user",
                            "text": f"用户冒烟 {marker}",
                            "sequence": 0,
                        },
                        {
                            "role": "assistant",
                            "text": f"助手冒烟 {marker}",
                            "sequence": 1,
                        },
                    ],
                },
            )
            created.raise_for_status()
            record_id = created.json()["id"]
            print(
                json.dumps(
                    {
                        "phase": "write",
                        "marker": marker,
                        "version": put_body["version"],
                        "record_id": record_id,
                    },
                    ensure_ascii=False,
                )
            )
            return put_body["version"], record_id, body["display_name"]


async def verify_phase(
    marker: str, version: int, record_id: str, display_name: str
) -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            response = await client.get(
                f"/api/v1/customer-services/{CS}",
                headers={"X-Tenant-ID": TENANT},
            )
            response.raise_for_status()
            body = response.json()
            assert body["display_name"] == display_name, body
            assert body["version"] == version, body

            detail = await client.get(
                f"/api/v1/call-records/{record_id}",
                headers={"X-Tenant-ID": TENANT},
            )
            detail.raise_for_status()
            payload = detail.json()
            assert payload["room_name"] == f"room-{marker}"
            assert len(payload["messages"]) == 2
            assert marker in payload["messages"][0]["text"]

            listing = await client.get(
                "/api/v1/call-records?limit=20",
                headers={"X-Tenant-ID": TENANT},
            )
            listing.raise_for_status()
            ids = [item["id"] for item in listing.json()["items"]]
            assert record_id in ids
            print(
                json.dumps(
                    {
                        "phase": "verify_ok",
                        "display_name": body["display_name"],
                        "version": body["version"],
                        "record_id": record_id,
                        "messages": len(payload["messages"]),
                    },
                    ensure_ascii=False,
                )
            )


async def main() -> None:
    marker = uuid.uuid4().hex[:8]
    version, record_id, display_name = await write_phase(marker)
    await verify_phase(marker, version, record_id, display_name)
    print("SMOKE_PASS")


if __name__ == "__main__":
    asyncio.run(main())
