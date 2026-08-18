# Appointments + Callbacks Phase 2 Implementation Plan

> **For agentic workers:** Use task-by-task execution. Steps use checkbox syntax.

**Goal:** 通话结束按转写抽取预约/回拨意向并落库（`source=voice_tool`），幂等可验收。

**Architecture:** 规则抽取服务 + call-records 钩子/显式 API；复用 Phase1 表与 repo。

**Tech Stack:** FastAPI, Pytest；无外部 LLM

## Global Constraints

- Spec: `docs/platform/superpowers/specs/2026-08-18-appointments-callbacks-phase2-extract-design.md`
- 不上生产；不自动 commit；Qwen 原生 Tool 不做

---

### Task 1: 抽取服务 + 单测

- [x] `services/intent_extract.py`：解析转写 → 决定 appointment / callback / skip
- [x] repo：`find_by_call_record_id`（InMemory + Postgres + Protocol）
- [x] 单测覆盖：预约 / 回拨 / 跳过 / 幂等

### Task 2: API 接线 + Prompt

- [x] `POST .../call-records/{id}/extract-intents`
- [x] create/update 自动触发（失败不阻断）
- [x] `create_app` 注入 appointment/callback repo
- [x] 更新 `DEMO_PACIFIC_PLATFORM_PROMPT`

### Task 3: 验证

- [x] pytest 通过
- [x] 更新 `TASKS.md`
- [x] Stage1 部署另授
