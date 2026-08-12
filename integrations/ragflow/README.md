# RAGFlow ↔ YinoVapi Integration

Phase 1: RAGFlow is the **Voice Agent knowledge retrieval engine**. Upload docs in RAGFlow UI (or bootstrap script); YinoVapi retrieves via HTTP.

## Layout

| Path | Role |
|---|---|
| `yinoai/ragflow` | Upstream RAGFlow source (do not fork for Phase 1) |
| `yinoai/integrations/ragflow` | Mapping, env templates, this runbook, demo docs |
| `yinoai/YinoVapi/services/platform-core` | `KnowledgeProvider` adapter + runtime |

## Runtime status (local)

| Item | Value |
|---|---|
| Web UI | http://127.0.0.1 |
| HTTP API | http://127.0.0.1:9380 |
| Demo dataset | `demo-dental-clinic` |
| Mapping tenants | `demo`, `demo-tenant` (Admin login user `demo`) |
| Local secrets | `.env` + `mapping.yaml` (**gitignored**) |
| Demo docs | `integrations/ragflow/demo-docs/*.md` |

Docker (WSL2 Ubuntu, data on D: VHDX):

```powershell
wsl -d Ubuntu -u root -- bash /mnt/d/Docker/downloads/fix-ragflow.sh
```

Embedding note: official TEI image pull may fail (Docker Hub). Local override runs a TEI-compatible `/embed` stub (`docker-compose.override.yml` → `tei-cpu`) so parse/retrieval smoke works. Replace with real TEI (`BAAI/bge-small-en-v1.5` or better Chinese model) when registry access is available.

## Quick start (RAGFlow already up)

1. Copy `.env.example` → `.env`, set `RAGFLOW_API_KEY` and paths.
2. Ensure `mapping.yaml` has real `dataset_ids` for tenant `demo`.
3. Smoke:

```powershell
cd yinoai\YinoVapi\services\platform-core
py -3.12 -m pip install -e ".[dev]"
py -3.12 -m pytest -q
# load integrations/ragflow/.env into the shell, then:
py -3.12 -m platform_core.retrieve --tenant demo --q "诊所营业时间是什么？"
```

Or:

```powershell
py -3.12 scripts\retrieve_demo.py
```

(On Windows, prefer UTF-8 / `PYTHONUTF8=1` so Chinese CLI args are not garbled.)

## Retrieval API used

`POST {RAGFLOW_BASE_URL}/api/v1/retrieval`  
Header: `Authorization: Bearer {API_KEY}`  
Body: `{ "question", "dataset_ids", "top_k", "similarity_threshold" }`

## Admin Demo 最小闭环（已接入）

```text
Admin 浏览器(:3003) ──► platform-core BFF(:8787) ──► RAGFlow(:9380)
       × 禁止直连 RAGFlow API Key
```

1. 确保 RAGFlow 已启动，且 `integrations/ragflow/.env` + `mapping.yaml` 就绪  
2. 启动 BFF：

```powershell
cd yinoai\YinoVapi\services\platform-core
py -3.12 -m pip install -e ".[demo]"
py -3.12 -m platform_core.knowledge_demo_server
```

3. Admin `.env.development`：

```text
VITE_KNOWLEDGE_READY=true
VITE_KNOWLEDGE_API_BASE=http://127.0.0.1:8787/
```

4. 打开 `http://127.0.0.1:3003/#/login`（demo/demo123）→ **知识库**：只读文档列表 + 试问检索  

Architecture (locked):

```text
Admin browser ──×──► RAGFlow
Platform Core KnowledgeRuntime ──► RagflowProvider ──HTTP──► RAGFlow /api/v1/retrieval
```

## Phase 2 (not now)

- Dataset-per-tenant mapping store
- Proxy Admin knowledge upload to RAGFlow
- Bind Voice Agent Instance → published knowledge version
- Swap TEI stub for production embedding model
