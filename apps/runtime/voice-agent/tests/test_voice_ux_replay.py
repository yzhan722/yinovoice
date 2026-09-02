from __future__ import annotations

from uuid import UUID

import httpx
import pytest
from hardening_support import FakePlatform

from yino_voice_agent.replay import ReplayEngine, ReplayEvent, ReplayFixture

TENANT = UUID("aaaaaaaa-0000-4000-8000-000000000001")
SERVICE = UUID("aaaaaaaa-0000-4000-8000-0000000000aa")


def _engine(http: httpx.AsyncClient) -> ReplayEngine:
    return ReplayEngine(
        http=http,
        tenant_id=TENANT,
        session_id="ux-room",
        customer_service_id=SERVICE,
    )


@pytest.mark.asyncio
async def test_ux_replay_fixtures_are_deterministic() -> None:
    platform = FakePlatform()
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        engine = _engine(http)
        result = await engine.run(
            ReplayFixture(
                schema_version=1,
                events=(
                    ReplayEvent(0, "runtime", "session_start", {}),
                    ReplayEvent(100, "runtime", "speech_start", {}),
                    ReplayEvent(400, "runtime", "audio_output_cancel", {}),
                    ReplayEvent(800, "runtime", "speech_end", {}),
                    ReplayEvent(
                        900,
                        "runtime",
                        "user_final",
                        {"text": "hello-user", "item_id": "u1"},
                    ),
                    ReplayEvent(
                        1000,
                        "qwen",
                        "assistant_final",
                        {"spoken": "ok", "tool_name": "check_availability"},
                    ),
                    ReplayEvent(9000, "runtime", "speech_start", {}),
                    ReplayEvent(20000, "runtime", "hangup", {}),
                ),
            )
        )
    assert result.greeting_count <= 1
    assert result.finish_count == 1
    assert result.silence_prompt_count <= 2
    assert "check_availability" in result.tool_names


@pytest.mark.asyncio
async def test_ux_replay_qwen_disconnect_finishes_once() -> None:
    platform = FakePlatform()
    async with httpx.AsyncClient(
        transport=platform, base_url="http://platform.test"
    ) as http:
        engine = _engine(http)
        result = await engine.run(
            ReplayFixture(
                schema_version=1,
                events=(
                    ReplayEvent(0, "runtime", "session_start", {}),
                    ReplayEvent(50, "qwen", "qwen_disconnect", {}),
                ),
            )
        )
    assert result.finish_count == 1
    assert "qwen_error" in result.errors
    assert result.greeting_count <= 1
