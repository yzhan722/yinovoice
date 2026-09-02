"""Fake telephony inbound boundary for future SIP adapters."""

from .inbound import (
    FakeDestinationResolver,
    FakeInboundProvider,
    InboundCallAdapter,
    NormalizedInboundCall,
    ResolvedDestination,
    RuntimeDispatch,
)
from .resolver import PlatformDestinationResolver

__all__ = [
    "FakeDestinationResolver",
    "FakeInboundProvider",
    "InboundCallAdapter",
    "NormalizedInboundCall",
    "PlatformDestinationResolver",
    "ResolvedDestination",
    "RuntimeDispatch",
]
