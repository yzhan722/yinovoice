"""Optional local turn demo API.

  py -3.12 -m pip install -e ".[demo,dev]"
  py -3.12 -m platform_core.api.turn_server
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from platform_core.config.loader import InstanceRepository
from platform_core.providers.knowledge.base import KnowledgeChunk
from platform_core.providers.knowledge.fake import FakeKnowledgeProvider
from platform_core.providers.model.fake import FakeModelProvider
from platform_core.runtime.knowledge import KnowledgeRuntime
from platform_core.runtime.turn import TurnInput
from platform_core.runtime.voice_agent import VoiceAgentOrchestrator

app = FastAPI(title="Yino Voice Turn Demo", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3003", "http://localhost:3003"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _build_orchestrator() -> VoiceAgentOrchestrator:
    knowledge = KnowledgeRuntime(
        FakeKnowledgeProvider(
            {
                "demo": [
                    KnowledgeChunk(
                        content="诊所营业时间为周一至周日 08:30–17:30（无休假门诊）。",
                        score=0.95,
                        document_name="营业时间.txt",
                    ),
                    KnowledgeChunk(
                        content="地址：常州市新北区通江南路266号。",
                        score=0.9,
                        document_name="地址.txt",
                    ),
                ]
            }
        )
    )
    return VoiceAgentOrchestrator(
        instances=InstanceRepository(),
        knowledge=knowledge,
        model=FakeModelProvider(),
    )


_orchestrator = _build_orchestrator()


class TurnRequest(BaseModel):
    instance_id: str = Field(default="1001")
    user_text: str
    confirm_tool_call_id: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/voice/turn")
async def voice_turn(body: TurnRequest) -> dict[str, Any]:
    try:
        out = await _orchestrator.handle_turn(
            TurnInput(
                instance_id=body.instance_id,
                user_text=body.user_text,
                confirm_tool_call_id=body.confirm_tool_call_id,
            )
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "code": 0,
        "data": {
            "reply_text": out.reply_text,
            "knowledge_used": out.knowledge_used,
            "actions": [
                {"type": a.type, "status": a.status, "detail": a.detail} for a in out.actions
            ],
            "pending_confirmations": [
                {
                    "tool_call_id": p.tool_call_id,
                    "tool_name": p.tool_name,
                    "arguments": p.arguments,
                    "reason": p.reason,
                }
                for p in out.pending_confirmations
            ],
        },
    }


def main() -> None:
    import uvicorn

    uvicorn.run(
        "platform_core.api.turn_server:app",
        host="127.0.0.1",
        port=8788,
        reload=False,
    )


if __name__ == "__main__":
    main()
