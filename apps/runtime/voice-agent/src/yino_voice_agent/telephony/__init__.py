"""Fake telephony inbound boundary and LiveKit SIP adapter."""

from .dispatch import resolve_runtime_dispatch, resolve_sip_inbound_dispatch
from .inbound import (
    FakeDestinationResolver,
    FakeInboundProvider,
    InboundCallAdapter,
    NormalizedInboundCall,
    ResolvedDestination,
    RuntimeDispatch,
)
from .livekit_sip import (
    FrozenUtcClock,
    coerce_presented_number_to_e164,
    is_sip_participant,
    normalize_livekit_sip_participant,
)
from .resolver import PlatformDestinationResolver

__all__ = [
    "FakeDestinationResolver",
    "FakeInboundProvider",
    "FrozenUtcClock",
    "InboundCallAdapter",
    "NormalizedInboundCall",
    "PlatformDestinationResolver",
    "ResolvedDestination",
    "RuntimeDispatch",
    "coerce_presented_number_to_e164",
    "is_sip_participant",
    "normalize_livekit_sip_participant",
    "resolve_runtime_dispatch",
    "resolve_sip_inbound_dispatch",
]
