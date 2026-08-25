from __future__ import annotations

import json
from uuid import UUID

from yino_platform_api.domain.phone_number import normalize_e164


def build_livekit_sip_plan(
    *,
    e164_number: str,
    tenant_id: UUID,
    customer_service_id: UUID,
    config_version: int,
) -> dict[str, object]:
    e164 = normalize_e164(e164_number)
    metadata = {
        "customer_service_id": str(customer_service_id),
        "tenant_id": str(tenant_id),
        "config_version": config_version,
        "channel": "sip",
        "callee_number": e164,
    }
    encoded = json.dumps(metadata, separators=(",", ":"), sort_keys=True)
    return {
        "dry_run": True,
        "inbound_trunk": {
            "name": f"yino-inbound-{e164}",
            "numbers": [e164],
            "krisp_enabled": False,
            "metadata": encoded,
        },
        "dispatch_rule": {
            "name": f"yino-dispatch-{e164}",
            "trunk_ids": ["<replace-after-create>"],
            "room_prefix": "sip-",
            "metadata": encoded,
        },
        "agent_dispatch_metadata": metadata,
    }
