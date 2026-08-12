"""Deterministic fake model for offline orchestrator tests and demos."""

from __future__ import annotations

from platform_core.providers.model.base import ModelRequest, ModelResponse
from platform_core.runtime.turn import ToolCallRequest


class FakeModelProvider:
    """Keyword-driven stub: knowledge Q&A, booking intent, handoff, confirm."""

    async def complete(self, request: ModelRequest) -> ModelResponse:
        text = (request.user_text or "").strip()
        tool_names = {t.name for t in request.tools}

        if request.confirm_tool_call_id and "booking" in tool_names:
            return ModelResponse(
                reply_text="好的，我现在为您提交预约。",
                tool_calls=[
                    ToolCallRequest(
                        id=request.confirm_tool_call_id,
                        name="booking",
                        arguments={"slot": "近期空档", "patient_name": "来电者"},
                    )
                ],
            )

        if any(k in text for k in ("转人工", "人工客服", "找人工")) and "handoff" in tool_names:
            return ModelResponse(
                reply_text="好的，我帮您转接人工。",
                tool_calls=[
                    ToolCallRequest(
                        id="tc-handoff-1",
                        name="handoff",
                        arguments={"reason": text},
                    )
                ],
            )

        if any(k in text for k in ("预约", "挂号", "约个")) and "booking" in tool_names:
            return ModelResponse(
                reply_text="可以为您预约。请确认是否现在登记预约意向？",
                tool_calls=[
                    ToolCallRequest(
                        id="tc-booking-1",
                        name="booking",
                        arguments={"slot": "明天上午", "patient_name": "来电者"},
                    )
                ],
            )

        if request.knowledge_block.strip() and any(
            k in text for k in ("营业", "几点", "时间", "地址", "在哪", "洁牙", "多少钱")
        ):
            # Prefer first knowledge line after header for a short spoken answer.
            first = request.knowledge_block.strip().split("\n\n", 1)[0]
            body = first.split("\n", 1)[-1].strip() if "\n" in first else first
            return ModelResponse(reply_text=f"根据资料，{body}")

        if "08:30" in request.system_prompt and any(k in text for k in ("营业", "几点", "时间")):
            return ModelResponse(reply_text="诊所营业时间是周一至周日 08:30–17:30。")

        return ModelResponse(
            reply_text="您好，我是诊所前台客服。请问需要咨询营业时间、项目，还是预约？"
        )
