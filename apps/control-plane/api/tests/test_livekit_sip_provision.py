from uuid import uuid4

from yino_platform_api.services.livekit_sip import build_livekit_sip_plan


def test_dry_run_plan_contains_dispatch_metadata_without_secrets() -> None:
    tenant_id = uuid4()
    service_id = uuid4()
    plan = build_livekit_sip_plan(
        e164_number="+61 400 000 001",
        tenant_id=tenant_id,
        customer_service_id=service_id,
        config_version=4,
    )
    assert plan["dry_run"] is True
    trunk = plan["inbound_trunk"]
    rule = plan["dispatch_rule"]
    metadata = plan["agent_dispatch_metadata"]
    assert trunk["numbers"] == ["+61400000001"]
    assert trunk["name"] == "yino-inbound-+61400000001"
    assert rule["room_prefix"] == "sip-"
    assert rule["trunk_ids"] == ["<replace-after-create>"]
    assert metadata == {
        "customer_service_id": str(service_id),
        "tenant_id": str(tenant_id),
        "config_version": 4,
        "channel": "sip",
        "callee_number": "+61400000001",
    }
    dumped = str(plan)
    assert "API" not in dumped.upper() or "api_key" not in dumped
    assert "secret" not in dumped.lower()
