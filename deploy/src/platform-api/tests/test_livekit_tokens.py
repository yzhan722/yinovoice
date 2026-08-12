from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi.testclient import TestClient
from livekit import api

from yino_platform_api.app import create_app
from yino_platform_api.domain.customer_service import CustomerServiceInstance
from yino_platform_api.repositories.customer_services import (
    InMemoryCustomerServiceRepository,
)
from yino_platform_api.services.livekit_tokens import (
    LiveKitAgentDispatcher,
    LiveKitTokenIssuer,
)


def decoded_jwt_payload(token: str) -> dict[str, Any]:
    encoded = token.split(".")[1]
    encoded += "=" * (-len(encoded) % 4)
    return json.loads(base64.urlsafe_b64decode(encoded))


@dataclass
class RecordingDispatcher:
    calls: list[dict[str, str]] = field(default_factory=list)
    failure: Exception | None = None

    async def dispatch(
        self,
        *,
        agent_name: str,
        room_name: str,
        metadata: str,
    ) -> None:
        if self.failure is not None:
            raise self.failure
        self.calls.append(
            {
                "agent_name": agent_name,
                "room_name": room_name,
                "metadata": metadata,
            }
        )


@pytest.mark.asyncio
async def test_livekit_dispatcher_uses_authenticated_agent_dispatch_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructor_calls: list[dict[str, str]] = []
    requests: list[api.CreateAgentDispatchRequest] = []
    closed = False

    class FakeAgentDispatchService:
        async def create_dispatch(
            self,
            request: api.CreateAgentDispatchRequest,
        ) -> None:
            requests.append(request)

    class FakeLiveKitAPI:
        agent_dispatch = FakeAgentDispatchService()

        async def __aenter__(self) -> FakeLiveKitAPI:
            return self

        async def __aexit__(self, *_args: object) -> None:
            nonlocal closed
            closed = True

    def fake_livekit_api(**kwargs: str) -> FakeLiveKitAPI:
        constructor_calls.append(kwargs)
        return FakeLiveKitAPI()

    monkeypatch.setattr(
        "yino_platform_api.services.livekit_tokens.api.LiveKitAPI",
        fake_livekit_api,
    )
    dispatcher = LiveKitAgentDispatcher(
        api_url="http://localhost:7880",
        api_key="devkey",
        api_secret="secret",
    )

    await dispatcher.dispatch(
        agent_name="yino-customer-service",
        room_name="yino-opaque-room",
        metadata='{"config_version":4}',
    )

    assert constructor_calls == [
        {
            "url": "http://localhost:7880",
            "api_key": "devkey",
            "api_secret": "secret",
        }
    ]
    assert len(requests) == 1
    assert requests[0].agent_name == "yino-customer-service"
    assert requests[0].room == "yino-opaque-room"
    assert requests[0].metadata == '{"config_version":4}'
    assert closed is True


@pytest.mark.asyncio
async def test_dispatch_is_server_side_and_browser_token_contains_no_runtime_data(
    ids,
) -> None:
    instance = CustomerServiceInstance.demo(
        instance_id=ids.instance_id,
        tenant_id=ids.tenant_id,
    )
    dispatcher = RecordingDispatcher()
    issuer = LiveKitTokenIssuer(
        api_key="devkey",
        api_secret="secret",
        server_url="ws://localhost:7880",
        agent_name="yino-customer-service",
        dispatcher=dispatcher,
    )

    join = await issuer.issue(instance, "browser-user-1")
    claims = api.TokenVerifier("devkey", "secret").verify(join.token)
    payload = decoded_jwt_payload(join.token)
    serialized_payload = json.dumps(payload, separators=(",", ":"))

    assert dispatcher.calls == [
        {
            "agent_name": "yino-customer-service",
            "room_name": join.room_name,
            "metadata": json.dumps(
                {
                    "customer_service_id": str(instance.id),
                    "tenant_id": str(instance.tenant_id),
                    "config_version": instance.version,
                },
                separators=(",", ":"),
            ),
        }
    ]
    assert join.server_url == "ws://localhost:7880"
    assert join.room_name.startswith("yino-")
    assert str(instance.id) not in join.room_name
    assert claims.video.room_join is True
    assert claims.video.room == join.room_name
    assert claims.video.can_publish is True
    assert claims.video.can_subscribe is True
    assert claims.video.can_publish_data is False
    assert list(claims.video.can_publish_sources) == ["microphone"]
    assert not claims.video.room_admin
    assert payload["exp"] - payload["nbf"] <= 600
    assert "roomConfig" not in payload
    assert "attributes" not in payload
    assert str(instance.id) not in serialized_payload
    assert str(instance.tenant_id) not in serialized_payload
    assert "customer_service_id" not in serialized_payload


def test_livekit_token_endpoint_is_tenant_scoped_and_dispatches_only_authorized_service(
    ids,
) -> None:
    instance = CustomerServiceInstance.demo(
        instance_id=ids.instance_id,
        tenant_id=ids.tenant_id,
    )
    repository = InMemoryCustomerServiceRepository([instance])
    dispatcher = RecordingDispatcher()
    client = TestClient(create_app(repository, agent_dispatcher=dispatcher))

    denied = client.post(
        f"/api/v1/customer-services/{ids.instance_id}/livekit-token",
        headers={"X-Tenant-ID": str(ids.other_tenant_id)},
        json={"participant_identity": "browser-user-1"},
    )

    assert denied.status_code == 404
    assert dispatcher.calls == []

    response = client.post(
        f"/api/v1/customer-services/{ids.instance_id}/livekit-token",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
        json={"participant_identity": "browser-user-1"},
    )

    assert response.status_code == 200
    assert len(dispatcher.calls) == 1
    assert set(response.json()) == {
        "server_url",
        "room_name",
        "participant_identity",
        "token",
    }


def test_dispatch_failure_returns_safe_error_and_never_issues_token(ids) -> None:
    instance = CustomerServiceInstance.demo(
        instance_id=ids.instance_id,
        tenant_id=ids.tenant_id,
    )
    repository = InMemoryCustomerServiceRepository([instance])
    dispatcher = RecordingDispatcher(
        failure=RuntimeError("upstream secret diagnostics")
    )
    client = TestClient(create_app(repository, agent_dispatcher=dispatcher))

    response = client.post(
        f"/api/v1/customer-services/{ids.instance_id}/livekit-token",
        headers={"X-Tenant-ID": str(ids.tenant_id)},
        json={"participant_identity": "browser-user-1"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "LiveKit voice session is temporarily unavailable"
    }
    assert "token" not in response.text
    assert "upstream secret diagnostics" not in response.text
