"""Normalize LiveKit SIP participants into Yino inbound calls.

Production SIP does not keep a process-global seen-call-id set. Duplicate Job
dedup, if ever proven, must be designed at the LiveKit dispatch boundary.
Exactly-once finish remains CallLifecycleClient's responsibility.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Protocol

from ..runtime_config import RuntimeConfigurationError
from ..session_trace import redact_phone_numbers
from .inbound import NormalizedInboundCall

logger = logging.getLogger(__name__)

LIVEKIT_SIP_PROVIDER = "livekit_sip"
_E164 = re.compile(r"^\+[1-9]\d{7,14}$")
_SEPARATORS = re.compile(r"[\s\-()]")
_HIDDEN_CALLER = frozenset({"hidephonenumber", "anonymous", "restricted"})
_SIP_KIND_NAMES = frozenset({"PARTICIPANT_KIND_SIP", "SIP"})
# livekit 1.1.x: rtc.ParticipantKind.PARTICIPANT_KIND_SIP == 3
# Pass this to wait_for_participant(kind=...) without importing livekit.
LIVEKIT_SIP_PARTICIPANT_KIND = 3
_SIP_KIND_VALUE = LIVEKIT_SIP_PARTICIPANT_KIND


class UtcClock(Protocol):
    def now(self) -> datetime:
        """Return an aware UTC datetime."""


class SystemUtcClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FrozenUtcClock:
    def __init__(self, instant: datetime) -> None:
        if instant.tzinfo is None:
            raise ValueError("clock instant must be timezone-aware")
        self._instant = instant

    def now(self) -> datetime:
        return self._instant


def is_sip_participant(participant: object | None) -> bool:
    if participant is None:
        return False
    kind = getattr(participant, "kind", None)
    name = getattr(kind, "name", None)
    if isinstance(name, str) and name in _SIP_KIND_NAMES:
        return True
    value = getattr(kind, "value", kind)
    return value == _SIP_KIND_VALUE


def _attr(attributes: Mapping[str, object], key: str) -> str | None:
    raw = attributes.get(key)
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    return text or None


def coerce_presented_number_to_e164(raw: str) -> str | None:
    """Map China PSTN / SIP presentation to E.164, or None if unusable.

    Telecom trunks often send 0519…, 010…, 400…, or 11-digit mobiles
    without '+86'. Lookup and Platform bindings still use E.164.
    """

    compact = _SEPARATORS.sub("", raw.strip())
    if not compact:
        return None
    if compact.lower() in _HIDDEN_CALLER:
        return None
    if compact.startswith("+"):
        return compact if _E164.fullmatch(compact) else None
    if compact.startswith("00"):
        candidate = f"+{compact[2:]}"
        return candidate if _E164.fullmatch(candidate) else None
    if not compact.isdigit():
        return None
    if compact.startswith("86"):
        candidate = f"+{compact}"
        return candidate if _E164.fullmatch(candidate) else None
    if len(compact) == 11 and compact.startswith("1"):
        candidate = f"+86{compact}"
        return candidate if _E164.fullmatch(candidate) else None
    if compact.startswith(("400", "800")) and 10 <= len(compact) <= 11:
        candidate = f"+86{compact}"
        return candidate if _E164.fullmatch(candidate) else None
    if compact.startswith("95") and 8 <= len(compact) <= 12:
        candidate = f"+86{compact}"
        return candidate if _E164.fullmatch(candidate) else None
    if compact.startswith("0") and 10 <= len(compact) <= 12:
        candidate = f"+86{compact[1:]}"
        return candidate if _E164.fullmatch(candidate) else None
    return None


def _caller_number(raw: str | None) -> str | None:
    if raw is None:
        return None
    return coerce_presented_number_to_e164(raw)


def normalize_livekit_sip_participant(
    participant: object,
    *,
    room_name: str | None,
    clock: UtcClock | None = None,
) -> NormalizedInboundCall:
    if not is_sip_participant(participant):
        raise RuntimeConfigurationError("participant is not a LiveKit SIP caller")
    attributes = getattr(participant, "attributes", None)
    if not isinstance(attributes, Mapping):
        raise RuntimeConfigurationError("SIP participant attributes are missing")

    call_id_full = _attr(attributes, "sip.callIDFull")
    call_id = _attr(attributes, "sip.callID")
    provider_call_id = call_id_full or call_id
    if provider_call_id is None:
        raise RuntimeConfigurationError("SIP participant is missing sip.callID")

    callee = _attr(attributes, "sip.trunkPhoneNumber")
    if callee is None:
        raise RuntimeConfigurationError("SIP participant is missing callee number")
    callee_e164 = coerce_presented_number_to_e164(callee)
    if callee_e164 is None:
        raise RuntimeConfigurationError("callee number must be E.164")

    caller = _caller_number(_attr(attributes, "sip.phoneNumber"))
    instant = (clock or SystemUtcClock()).now()
    call = NormalizedInboundCall(
        provider=LIVEKIT_SIP_PROVIDER,
        provider_call_id=provider_call_id,
        caller_number=caller,
        callee_number=callee_e164,
        direction="inbound",
        connected_at=instant,
        room_name=room_name,
        trunk_id=_attr(attributes, "sip.trunkID"),
        rule_id=_attr(attributes, "sip.ruleID"),
    )
    logger.info(
        "sip inbound normalized provider=%s call_id=%s room=%s trunk_id=%s "
        "rule_id=%s caller_present=%s",
        call.provider,
        redact_phone_numbers(call.provider_call_id),
        redact_phone_numbers(call.room_name or "-"),
        redact_phone_numbers(call.trunk_id or "-"),
        redact_phone_numbers(call.rule_id or "-"),
        call.caller_number is not None,
    )
    return call
