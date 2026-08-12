"""VoiceAgentOrchestrator — in-project text-turn orchestration."""

from __future__ import annotations

from platform_core.config.loader import InstanceRepository
from platform_core.providers.model.base import ModelProvider, ModelRequest
from platform_core.providers.model.fake import FakeModelProvider
from platform_core.runtime.knowledge import KnowledgeRuntime
from platform_core.runtime.policy import PlatformPolicy
from platform_core.runtime.prompt import merge_system_prompt
from platform_core.runtime.turn import (
    Message,
    PendingConfirmation,
    TurnAction,
    TurnInput,
    TurnOutput,
)
from platform_core.tools.registry import ToolRegistry


class VoiceAgentOrchestrator:
    def __init__(
        self,
        *,
        instances: InstanceRepository,
        knowledge: KnowledgeRuntime,
        model: ModelProvider | None = None,
        tools: ToolRegistry | None = None,
        policy: PlatformPolicy | None = None,
    ) -> None:
        self._instances = instances
        self._knowledge = knowledge
        self._model = model or FakeModelProvider()
        self._tools = tools or ToolRegistry()
        self._policy = policy or PlatformPolicy()

    async def handle_turn(self, turn: TurnInput) -> TurnOutput:
        instance = self._instances.get_instance(turn.instance_id)
        template = self._instances.get_template(instance.template_id, instance.template_version)

        knowledge_block = await self._knowledge.retrieve_context(
            question=turn.user_text,
            tenant_id=instance.tenant_id,
            agent_id=instance.agent_id,
        )
        system_prompt = merge_system_prompt(
            instance=instance,
            template=template,
            knowledge_block=knowledge_block,
        )

        tool_ids = instance.tool_ids or template.default_tool_ids
        tool_specs = self._tools.specs_for(tool_ids)
        messages = list(turn.conversation) + [Message(role="user", content=turn.user_text)]

        model_out = await self._model.complete(
            ModelRequest(
                system_prompt=system_prompt,
                messages=messages,
                tools=tool_specs,
                user_text=turn.user_text,
                knowledge_block=knowledge_block,
                confirm_tool_call_id=turn.confirm_tool_call_id,
            )
        )

        confirmed: set[str] = set()
        if turn.confirm_tool_call_id:
            confirmed.add(turn.confirm_tool_call_id)

        actions: list[TurnAction] = []
        pending: list[PendingConfirmation] = []
        reply = model_out.reply_text

        for call in model_out.tool_calls:
            decision = self._policy.decide(
                call,
                user_text=turn.user_text,
                confirmed_ids=confirmed,
            )
            if decision.decision == "require_confirmation":
                pending.append(
                    PendingConfirmation(
                        tool_call_id=call.id,
                        tool_name=call.name,
                        arguments=dict(call.arguments),
                        reason=decision.reason,
                    )
                )
                actions.append(
                    TurnAction(
                        type=call.name,
                        status="pending_confirmation",
                        detail={"tool_call_id": call.id, "arguments": call.arguments},
                    )
                )
                if "确认" not in reply:
                    reply = f"{reply}请回复「确认」以便我继续办理。"
                continue

            if decision.decision == "block":
                actions.append(
                    TurnAction(
                        type=call.name,
                        status="blocked",
                        detail={"reason": decision.reason, "tool_call_id": call.id},
                    )
                )
                continue

            tool = self._tools.get(call.name)
            if tool is None:
                actions.append(
                    TurnAction(
                        type=call.name,
                        status="failed",
                        detail={"reason": "tool not registered"},
                    )
                )
                continue

            result = await tool.execute(dict(call.arguments))
            actions.append(
                TurnAction(
                    type=call.name,
                    status="executed" if result.ok else "failed",
                    detail={"message": result.message, **result.data},
                )
            )
            if result.ok and result.message:
                reply = result.message

        return TurnOutput(
            reply_text=reply,
            knowledge_used=knowledge_block,
            actions=actions,
            pending_confirmations=pending,
            system_prompt=system_prompt,
        )
