"""Dry-run LiveKit SIP inbound trunk + dispatch rule generator.

Does not call LiveKit or read real secrets.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID

API_SRC = Path(__file__).resolve().parents[1] / "apps" / "control-plane" / "api" / "src"
sys.path.insert(0, str(API_SRC))

from yino_platform_api.services.livekit_sip import build_livekit_sip_plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.add_argument("--e164", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--customer-service-id", required=True)
    parser.add_argument("--config-version", type=int, default=1)
    args = parser.parse_args()
    plan = build_livekit_sip_plan(
        e164_number=args.e164,
        tenant_id=UUID(args.tenant_id),
        customer_service_id=UUID(args.customer_service_id),
        config_version=args.config_version,
    )
    json.dump(plan, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
