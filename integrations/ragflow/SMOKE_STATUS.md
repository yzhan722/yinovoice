# RAGFlow P0 smoke status

- Web: http://127.0.0.1
- API: http://127.0.0.1:9380
- Embedding: `BAAI/bge-small-en-v1.5@Builtin` via **TEI-compatible stub** (`tei-cpu` override)
- Dataset: `demo-dental-clinic` / `b76cd0f08f0111f1872fd1221e3e7823`
- Mapping tenants: `demo`, `demo-tenant`
- Demo docs (7):
  - 营业时间与地址.md
  - 洁牙与常见问题.md
  - 预约须知.md
  - 医生与科室.md
  - 收费与支付.md
  - 转人工与投诉.md
  - 初诊与病历.md
- Secrets: local `.env`, `mapping.yaml` (gitignored)
- CLI: `python -m platform_core.retrieve --tenant demo --q "..."`

## Voice CS framework gap

- RAG retrieve: **ready**
- Model turn / Prompt merge / phone call loop: **not built yet** (next: text probe or Model-turn hook)
