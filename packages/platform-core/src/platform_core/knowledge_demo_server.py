"""Minimal demo BFF: Admin → Platform Core → RAGFlow (never expose API key to browser).

Run (after loading integrations/ragflow/.env):
  py -3.12 -m pip install -e ".[demo]"
  py -3.12 -m platform_core.knowledge_demo_server
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from platform_core.providers.knowledge.mapping import load_mapping
from platform_core.providers.knowledge.ragflow import RagflowProvider
from platform_core.runtime.knowledge import KnowledgeRuntime

DEFAULT_ENV_FILE = Path(__file__).resolve().parents[4] / "integrations" / "ragflow" / ".env"
# platform-core/src/platform_core → parents[4] = yinoai when layout is yinoai/YinoVapi/services/platform-core
# parents: 0=platform_core, 1=src, 2=platform-core, 3=services, 4=YinoVapi — wrong
# Fix: search known relative paths


def _find_env_file() -> Path | None:
    override = os.getenv("RAGFLOW_ENV_FILE", "").strip()
    if override:
        p = Path(override)
        return p if p.is_file() else None
    here = Path(__file__).resolve()
    candidates = [
        here.parents[4] / "integrations" / "ragflow" / ".env",  # …/YinoVapi → sibling integrations? no
        here.parents[5] / "integrations" / "ragflow" / ".env",  # yinoai/integrations
        Path("d:/project/yinoai/integrations/ragflow/.env"),
        Path("/mnt/d/project/yinoai/integrations/ragflow/.env"),
    ]
    # Walk up looking for yinoai/integrations/ragflow/.env
    for parent in here.parents:
        cand = parent / "integrations" / "ragflow" / ".env"
        if cand.is_file():
            return cand
        cand2 = parent / "yinoai" / "integrations" / "ragflow" / ".env"
        if cand2.is_file():
            return cand2
    for c in candidates:
        if c.is_file():
            return c
    return None


def load_dotenv_file() -> None:
    path = _find_env_file()
    if not path:
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
    # Prefer linux-friendly mapping path when under WSL-style mounts is not needed on Windows
    mapping = os.getenv("RAGFLOW_MAPPING_FILE", "")
    if mapping.startswith("/mnt/d/"):
        win = "d:/" + mapping[len("/mnt/d/") :]
        if Path(win).is_file():
            os.environ["RAGFLOW_MAPPING_FILE"] = win


load_dotenv_file()

app = FastAPI(title="Yino Knowledge Demo BFF", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3003",
        "http://localhost:3003",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RetrieveBody(BaseModel):
    question: str = Field(min_length=1)
    tenant_id: str | None = None
    top_k: int | None = None


def _tenant_id(explicit: str | None = None) -> str:
    return (explicit or os.getenv("RAGFLOW_DEMO_TENANT_ID") or "demo").strip() or "demo"


def _require_env() -> None:
    missing = [n for n in ("RAGFLOW_BASE_URL", "RAGFLOW_API_KEY", "RAGFLOW_MAPPING_FILE") if not os.getenv(n, "").strip()]
    if missing:
        raise HTTPException(status_code=503, detail="Missing env: " + ", ".join(missing))


async def _list_ragflow_docs() -> list[dict[str, Any]]:
    _require_env()
    mapping = load_mapping(os.environ["RAGFLOW_MAPPING_FILE"])
    tenant = mapping.for_tenant(_tenant_id())
    if tenant is None or not tenant.dataset_ids:
        return []
    dataset_id = tenant.dataset_ids[0]
    base = os.environ["RAGFLOW_BASE_URL"].rstrip("/")
    api_key = os.environ["RAGFLOW_API_KEY"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{base}/api/v1/datasets/{dataset_id}/documents",
            params={"page": 1, "page_size": 50},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resp.raise_for_status()
        body = resp.json()
    data = body.get("data") or {}
    docs = []
    if isinstance(data, dict):
        docs = data.get("docs") or data.get("documents") or data.get("list") or []
    elif isinstance(data, list):
        docs = data
    out = []
    for d in docs:
        if not isinstance(d, dict):
            continue
        run = str(d.get("run") or d.get("status") or "")
        chunks = int(d.get("chunk_count") or d.get("chunk_num") or 0)
        status = "done" if chunks > 0 and run.upper() in {"DONE", "SUCCESS", "3", ""} else "processing"
        if run.upper() == "DONE":
            status = "done"
        out.append(
            {
                "filId": str(d.get("id") or ""),
                "filName": str(d.get("name") or d.get("location") or "document"),
                "filSizeBytes": int(d.get("size") or 0),
                "filExtStatus": status,
                "filCreateTime": str(d.get("create_date") or d.get("create_time") or ""),
                "chunkCount": chunks,
                "datasetId": dataset_id,
            }
        )
    return out


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "code": 0,
        "data": {
            "ok": True,
            "knowledge_ready": bool(os.getenv("RAGFLOW_API_KEY")),
            "tenant": _tenant_id(),
            "env_file": str(_find_env_file() or ""),
        },
    }


@app.get("/api/knowledge/docs")
@app.post("/api/knowledge/docs")
async def knowledge_docs() -> dict[str, Any]:
    try:
        records = await _list_ragflow_docs()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — demo BFF fail soft
        raise HTTPException(status_code=502, detail=f"RAGFlow list failed: {exc}") from exc
    return {
        "code": 0,
        "data": {
            "records": records,
            "list": records,
            "total": len(records),
            "ready": True,
            "source": "ragflow",
        },
    }


@app.post("/api/knowledge/retrieve")
async def knowledge_retrieve(body: RetrieveBody) -> dict[str, Any]:
    _require_env()
    tenant_id = _tenant_id(body.tenant_id)
    provider = RagflowProvider.from_env()
    runtime = KnowledgeRuntime(provider)
    try:
        chunks = await provider.retrieve(question=body.question.strip(), tenant_id=tenant_id, top_k=body.top_k)
        context = runtime.format_context(chunks)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"RAGFlow retrieve failed: {exc}") from exc
    finally:
        await provider.aclose()
    return {
        "code": 0,
        "data": {
            "ready": True,
            "tenant_id": tenant_id,
            "question": body.question,
            "context": context,
            "chunks": [
                {
                    "content": c.content,
                    "score": c.score,
                    "document_name": c.document_name,
                    "document_id": c.document_id,
                    "chunk_id": c.chunk_id,
                }
                for c in chunks
            ],
        },
    }

def main() -> None:
    import uvicorn

    host = os.getenv("KNOWLEDGE_DEMO_HOST", "127.0.0.1")
    port = int(os.getenv("KNOWLEDGE_DEMO_PORT", "8787"))
    uvicorn.run("platform_core.knowledge_demo_server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
