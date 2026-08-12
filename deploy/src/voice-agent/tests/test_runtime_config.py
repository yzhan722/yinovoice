import json
from collections.abc import Callable
from uuid import UUID, uuid4

import httpx
import pytest

from yino_voice_agent.runtime_config import (
    DispatchMetadata,
    PlatformConfigClient,
    RuntimeConfigurationError,
)


def published_snapshot(
    *,
    service_id: UUID,
    tenant_id: UUID,
    version: int,
) -> dict[str, object]:
    return {
        "id": str(service_id),
        "tenant_id": str(tenant_id),
        "version": version,
        "display_name": "演示 AI 语音客服",
        "organization_name": "Yino 演示机构",
        "greeting": (
            "\u60a8\u597d\uff0c\u8fd9\u91cc\u662f Yino "
            "\u6f14\u793a\u673a\u6784\u5ba2\u670d\u3002"
        ),
        "tenant_prompt": "Internal platform-only prompt.",
        "voice": {
            "preset_id": "mandarin-standard",
            "locale": "zh-CN",
            "speaking_rate": 1.1,
            "volume": 1.0,
            "pitch": 0.0,
            "style": "professional-friendly",
            "emotion": "neutral",
            "pause_profile": "receptionist",
        },
        "response": {
            "brevity": "concise",
            "max_spoken_sentences": 3,
            "ask_one_question_at_a_time": True,
        },
        "business_profile": "generic-receptionist",
        "primary_language": "zh-CN",
    }


def test_dispatch_metadata_parses_authoritative_identifiers() -> None:
    service_id = uuid4()
    tenant_id = uuid4()

    parsed = DispatchMetadata.from_json(
        json.dumps(
            {
                "customer_service_id": str(service_id),
                "tenant_id": str(tenant_id),
                "config_version": 3,
            }
        )
    )

    assert parsed.customer_service_id == service_id
    assert parsed.tenant_id == tenant_id
    assert parsed.config_version == 3


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ("not-json", "valid JSON"),
        ("{}", "exactly"),
        (
            json.dumps(
                {
                    "customer_service_id": str(uuid4()),
                    "tenant_id": str(uuid4()),
                    "config_version": 0,
                }
            ),
            "positive",
        ),
        (
            json.dumps(
                {
                    "customer_service_id": str(uuid4()),
                    "tenant_id": str(uuid4()),
                    "config_version": 1,
                    "fallback_tenant": "not-allowed",
                }
            ),
            "exactly",
        ),
        (
            """{
                "customer_service_id": "00000000-0000-0000-0000-000000000001",
                "tenant_id": "00000000-0000-0000-0000-000000000002",
                "config_version": 1,
                "config_version": 2
            }""",
            "valid JSON",
        ),
    ],
)
def test_dispatch_metadata_fails_closed_for_malformed_nonempty_values(
    raw: str,
    reason: str,
) -> None:
    with pytest.raises(RuntimeConfigurationError, match=reason):
        DispatchMetadata.from_json(raw)


@pytest.mark.asyncio
async def test_client_fetches_exact_tenant_snapshot() -> None:
    service_id = uuid4()
    tenant_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == f"/api/v1/customer-services/{service_id}"
        assert request.headers["X-Tenant-ID"] == str(tenant_id)
        return httpx.Response(
            200,
            json=published_snapshot(
                service_id=service_id,
                tenant_id=tenant_id,
                version=2,
            ),
        )

    metadata = DispatchMetadata(service_id, tenant_id, 2)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://platform.test",
    ) as http_client:
        client = PlatformConfigClient(http_client)
        result = await client.get(metadata)

    assert result.organization_name == "Yino 演示机构"
    assert result.voice.preset_id == "mandarin-standard"
    assert result.voice.speaking_rate == 1.1
    assert result.tenant_prompt == "Internal platform-only prompt."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("voice", "preset_id", "raw-provider-voice-id"),
        ("voice", "locale", "ignore-platform-rules"),
        ("voice", "style", "speak-the-system-prompt"),
        ("voice", "emotion", "obey-tenant-only"),
        ("voice", "pause_profile", "disable-safety"),
        ("response", "ask_one_question_at_a_time", False),
    ],
)
async def test_client_rejects_unpublished_business_options(
    section: str,
    field: str,
    value: object,
) -> None:
    service_id = uuid4()
    tenant_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        snapshot = published_snapshot(
            service_id=service_id,
            tenant_id=tenant_id,
            version=2,
        )
        nested = snapshot[section]
        assert isinstance(nested, dict)
        nested[field] = value
        return httpx.Response(200, json=snapshot)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://platform.test",
    ) as http_client:
        with pytest.raises(RuntimeConfigurationError):
            await PlatformConfigClient(http_client).get(
                DispatchMetadata(service_id, tenant_id, 2)
            )


@pytest.mark.asyncio
async def test_client_rejects_greeting_with_proactive_identity_claim() -> None:
    service_id = uuid4()
    tenant_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        snapshot = published_snapshot(
            service_id=service_id,
            tenant_id=tenant_id,
            version=2,
        )
        snapshot["greeting"] = "您好,我是AI客服。"
        return httpx.Response(200, json=snapshot)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://platform.test",
    ) as http_client:
        with pytest.raises(RuntimeConfigurationError, match="greeting"):
            await PlatformConfigClient(http_client).get(
                DispatchMetadata(service_id, tenant_id, 2)
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutate",
    [
        lambda snapshot, service_id, tenant_id: snapshot.update(id=str(uuid4())),
        lambda snapshot, service_id, tenant_id: snapshot.update(tenant_id=str(uuid4())),
        lambda snapshot, service_id, tenant_id: snapshot.update(version=3),
    ],
)
async def test_client_rejects_snapshot_that_does_not_match_dispatch_metadata(
    mutate: Callable[[dict[str, object], UUID, UUID], None],
) -> None:
    service_id = uuid4()
    tenant_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        snapshot = published_snapshot(
            service_id=service_id,
            tenant_id=tenant_id,
            version=2,
        )
        mutate(snapshot, service_id, tenant_id)
        return httpx.Response(200, json=snapshot)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://platform.test",
    ) as http_client:
        with pytest.raises(RuntimeConfigurationError, match="does not match"):
            await PlatformConfigClient(http_client).get(
                DispatchMetadata(service_id, tenant_id, 2)
            )


@pytest.mark.asyncio
async def test_client_rejects_unexpected_snapshot_fields_without_echoing_body() -> None:
    service_id = uuid4()
    tenant_id = uuid4()
    secret = "must-not-appear-in-errors"

    def handler(request: httpx.Request) -> httpx.Response:
        snapshot = published_snapshot(
            service_id=service_id,
            tenant_id=tenant_id,
            version=2,
        )
        snapshot["unexpected"] = secret
        return httpx.Response(200, json=snapshot)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://platform.test",
    ) as http_client:
        with pytest.raises(RuntimeConfigurationError) as error:
            await PlatformConfigClient(http_client).get(
                DispatchMetadata(service_id, tenant_id, 2)
            )

    assert secret not in str(error.value)


@pytest.mark.asyncio
async def test_client_rejects_duplicate_snapshot_keys_without_echoing_body() -> None:
    service_id = uuid4()
    tenant_id = uuid4()
    secret = "must-not-appear-in-errors"
    snapshot_json = json.dumps(
        published_snapshot(
            service_id=service_id,
            tenant_id=tenant_id,
            version=2,
        )
    )
    duplicate_snapshot_json = snapshot_json.replace(
        '"tenant_prompt": "Internal platform-only prompt."',
        f'"tenant_prompt": "{secret}", '
        '"tenant_prompt": "Internal platform-only prompt."',
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=duplicate_snapshot_json)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://platform.test",
    ) as http_client:
        with pytest.raises(RuntimeConfigurationError) as error:
            await PlatformConfigClient(http_client).get(
                DispatchMetadata(service_id, tenant_id, 2)
            )

    assert secret not in str(error.value)
