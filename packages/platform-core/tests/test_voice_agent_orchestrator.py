from __future__ import annotations

from pathlib import Path

import pytest

from platform_core.config.loader import InstanceRepository, load_instance
from platform_core.providers.knowledge.base import KnowledgeChunk
from platform_core.providers.knowledge.fake import FakeKnowledgeProvider
from platform_core.providers.model.fake import FakeModelProvider
from platform_core.runtime.knowledge import KnowledgeRuntime
from platform_core.runtime.policy import PlatformPolicy
from platform_core.runtime.prompt import merge_system_prompt
from platform_core.runtime.turn import ToolCallRequest, TurnInput
from platform_core.runtime.voice_agent import VoiceAgentOrchestrator
from platform_core.tools.registry import ToolRegistry


ROOT = Path(__file__).resolve().parents[4]  # yinoai when layout …/yinoai/YinoVapi/services/platform-core
INTEGRATIONS = ROOT / "integrations" / "platform-core"


def _integrations_root() -> Path:
    if INTEGRATIONS.is_dir():
        return INTEGRATIONS
    # walk up
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "integrations" / "platform-core"
        if cand.is_dir():
            return cand
    raise RuntimeError("integrations/platform-core missing")


def test_load_demo_instance() -> None:
    root = _integrations_root()
    inst = load_instance(root / "instances" / "demo-1001.yaml")
    assert inst.instance_id == "1001"
    assert inst.tenant_id == "demo"
    assert inst.organization_name.startswith("常州太平洋口腔")
    assert "booking" in inst.tool_ids


def test_instance_repository() -> None:
    repo = InstanceRepository(_integrations_root())
    inst = repo.get_instance("1001")
    tpl = repo.get_template(inst.template_id, inst.template_version)
    assert tpl.template_id == "tpl-dental"
    assert "前台客服" in tpl.protected_prompt or "客服" in tpl.protected_prompt


def test_prompt_merge_includes_policy_and_knowledge() -> None:
    repo = InstanceRepository(_integrations_root())
    inst = repo.get_instance("1001")
    tpl = repo.get_template(inst.template_id, inst.template_version)
    prompt = merge_system_prompt(
        instance=inst,
        template=tpl,
        knowledge_block="[1] hours\n周一至周日 08:30–17:30",
    )
    assert "平台规则" in prompt
    assert "tenant_configuration_data_json" in prompt
    assert "retrieved_knowledge_reference" in prompt
    assert "08:30" in prompt


def test_policy_booking_requires_confirmation() -> None:
    policy = PlatformPolicy()
    call = ToolCallRequest(id="tc-1", name="booking", arguments={"slot": "明天"})
    d = policy.decide(call, user_text="我想预约")
    assert d.decision == "require_confirmation"
    d2 = policy.decide(call, user_text="确认", confirmed_ids={"tc-1"})
    assert d2.decision == "execute"


def test_policy_unknown_tool_blocked() -> None:
    policy = PlatformPolicy()
    call = ToolCallRequest(id="x", name="delete_all", arguments={})
    assert policy.decide(call, user_text="x").decision == "block"


@pytest.mark.asyncio
async def test_orchestrator_answers_from_knowledge() -> None:
    repo = InstanceRepository(_integrations_root())
    knowledge = KnowledgeRuntime(
        FakeKnowledgeProvider(
            {
                "demo": [
                    KnowledgeChunk(
                        content="诊所营业时间为周一至周日 08:30–17:30（无休假门诊）。",
                        score=0.95,
                        document_name="营业时间.txt",
                    )
                ]
            }
        )
    )
    orch = VoiceAgentOrchestrator(
        instances=repo,
        knowledge=knowledge,
        model=FakeModelProvider(),
        tools=ToolRegistry(),
    )
    out = await orch.handle_turn(TurnInput(instance_id="1001", user_text="诊所几点营业？"))
    assert "08:30" in out.reply_text
    assert out.knowledge_used
    assert "平台规则" in out.system_prompt


@pytest.mark.asyncio
async def test_orchestrator_booking_pending_then_confirm() -> None:
    repo = InstanceRepository(_integrations_root())
    knowledge = KnowledgeRuntime(FakeKnowledgeProvider({}))
    orch = VoiceAgentOrchestrator(
        instances=repo,
        knowledge=knowledge,
        model=FakeModelProvider(),
    )
    first = await orch.handle_turn(TurnInput(instance_id="1001", user_text="我想预约洗牙"))
    assert first.pending_confirmations
    assert first.pending_confirmations[0].tool_name == "booking"
    assert any(a.status == "pending_confirmation" for a in first.actions)

    confirm_id = first.pending_confirmations[0].tool_call_id
    second = await orch.handle_turn(
        TurnInput(
            instance_id="1001",
            user_text="确认",
            confirm_tool_call_id=confirm_id,
        )
    )
    assert any(a.type == "booking" and a.status == "executed" for a in second.actions)
    assert "预约" in second.reply_text or "登记" in second.reply_text


@pytest.mark.asyncio
async def test_orchestrator_handoff() -> None:
    repo = InstanceRepository(_integrations_root())
    knowledge = KnowledgeRuntime(FakeKnowledgeProvider({}))
    orch = VoiceAgentOrchestrator(
        instances=repo,
        knowledge=knowledge,
        model=FakeModelProvider(),
    )
    out = await orch.handle_turn(TurnInput(instance_id="1001", user_text="请帮我转人工"))
    assert any(a.type == "handoff" and a.status == "executed" for a in out.actions)
    assert "转人工" in out.reply_text or "回拨" in out.reply_text


@pytest.mark.asyncio
async def test_orchestrator_empty_knowledge_still_replies() -> None:
    repo = InstanceRepository(_integrations_root())
    knowledge = KnowledgeRuntime(FakeKnowledgeProvider({}))
    orch = VoiceAgentOrchestrator(
        instances=repo,
        knowledge=knowledge,
        model=FakeModelProvider(),
    )
    out = await orch.handle_turn(TurnInput(instance_id="1001", user_text="你好"))
    assert out.reply_text
    assert out.knowledge_used == ""
