from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol
from uuid import uuid4

from livekit import api

from ..domain.customer_service import CustomerServiceInstance


class AgentDispatcher(Protocol):
    """Server-side boundary for creating one named-agent dispatch."""

    async def dispatch(
        self,
        *,
        agent_name: str,
        room_name: str,
        metadata: str,
    ) -> None: ...


class LiveKitDispatchError(RuntimeError):
    """Raised without leaking upstream details when dispatch cannot be created."""


class LiveKitAgentDispatcher:
    """Create explicit dispatches through LiveKit's authenticated server API."""

    def __init__(
        self,
        *,
        api_url: str,
        api_key: str,
        api_secret: str,
    ) -> None:
        self._api_url = api_url
        self._api_key = api_key
        self._api_secret = api_secret

    async def dispatch(
        self,
        *,
        agent_name: str,
        room_name: str,
        metadata: str,
    ) -> None:
        async with api.LiveKitAPI(
            url=self._api_url,
            api_key=self._api_key,
            api_secret=self._api_secret,
        ) as livekit:
            await livekit.agent_dispatch.create_dispatch(
                api.CreateAgentDispatchRequest(
                    agent_name=agent_name,
                    room=room_name,
                    metadata=metadata,
                )
            )


@dataclass(frozen=True, slots=True)
class LiveKitJoin:
    server_url: str
    room_name: str
    participant_identity: str
    token: str


class LiveKitTokenIssuer:
    def __init__(
        self,
        *,
        api_key: str,
        api_secret: str,
        server_url: str,
        agent_name: str,
        dispatcher: AgentDispatcher,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._server_url = server_url
        self._agent_name = agent_name
        self._dispatcher = dispatcher

    async def issue(
        self,
        instance: CustomerServiceInstance,
        participant_identity: str,
    ) -> LiveKitJoin:
        room_name = f"yino-{uuid4().hex}"
        metadata = json.dumps(
            {
                "customer_service_id": str(instance.id),
                "tenant_id": str(instance.tenant_id),
                "config_version": instance.version,
            },
            separators=(",", ":"),
        )
        try:
            await self._dispatcher.dispatch(
                agent_name=self._agent_name,
                room_name=room_name,
                metadata=metadata,
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            raise LiveKitDispatchError(
                "LiveKit agent dispatch could not be created"
            ) from error

        token = (
            api.AccessToken(self._api_key, self._api_secret)
            .with_identity(participant_identity)
            .with_ttl(timedelta(minutes=10))
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                    can_publish_data=False,
                    can_publish_sources=["microphone"],
                )
            )
            .to_jwt()
        )
        return LiveKitJoin(
            server_url=self._server_url,
            room_name=room_name,
            participant_identity=participant_identity,
            token=token,
        )
