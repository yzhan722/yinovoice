"""Shared-secret gate for inbound phone-number lookup.

Runtime (A) must send this header. An empty configured token fails closed:
lookup never enumerates mappings on the public internet.
"""

from __future__ import annotations

import hmac

PHONE_LOOKUP_HEADER = "X-Phone-Lookup-Token"


def phone_lookup_token_matches(expected: str | None, given: str | None) -> bool:
    wanted = (expected or "").strip()
    provided = (given or "").strip()
    if not wanted or not provided:
        return False
    if len(wanted) != len(provided):
        hmac.compare_digest(wanted, wanted)
        return False
    return hmac.compare_digest(wanted, provided)
