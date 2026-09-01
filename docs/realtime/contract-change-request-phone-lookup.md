# Contract Change Request

Requester: DEV-A
Contract: `GET /api/v1/phone-numbers/lookup?number=<callee>`
Problem: Runtime must distinguish unknown vs disabled vs lookup failure without starting the wrong tenant agent. Public unauthenticated lookup would enumerate DID → tenant mappings.
Existing behavior: Platform returns **404** when the number is missing **or** `enabled=false`. A 200 body is a full `PhoneNumberView`. **2026-09-01:** lookup requires header `X-Phone-Lookup-Token` matching Control Plane `PHONE_LOOKUP_TOKEN`. Empty token or missing/wrong header → **401**. Runtime sends the same env value; unset token fails closed before HTTP.
Requested input/output: Keep 200 with `tenant_id`, `voice_agent_instance_id`, `config_version`, `enabled`. Optionally return 200 + `enabled=false` for disabled numbers so Runtime can log a distinct `destination is disabled` without treating it as unknown. Not required to unblock inbound SIP: Runtime already fail-closes on 404 and on `enabled=false`.
Backward compatibility: Additive. Do not remove current 404-for-disabled behavior without a versioned agreement.
Tests required: Platform lookup tests for unknown, disabled, and extra view fields. Runtime already covers 404, `enabled=false`, timeout, and HTTP 500.
Blocks current work? no
