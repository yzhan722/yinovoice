# Voice Agent Instance A3 Soft Delete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为语音实例补齐软删除 / 恢复 / 条件硬删（purge），并在「我的实例」可操作。

**Architecture:** `voice_agent_instances.deleted_at`；默认列表过滤；GET/PUT/token 对已软删 404；`POST .../purge` 仅已软删且无关联通话（含已软删通话）时物理删除；前端对齐通话记录列表交互。

**Tech Stack:** FastAPI, Alembic, SQLAlchemy, Vue 3, Vitest, Pytest

## Global Constraints

- 规格：`docs/platform/superpowers/specs/2026-08-17-voice-agent-instance-a3-soft-delete-design.md`
- 主仓库：`E:\Repos\yinovoice`
- 只改本地 worktree/主仓；先 Stage1；不上生产；不自动 commit

---

### Task 1: Domain + migration + ORM

- [x] `CustomerServiceInstance.deleted_at`
- [x] Alembic `20260817_0003_voice_agent_instances_soft_delete`
- [x] `VoiceAgentInstance.deleted_at`

### Task 2: Repos + routes + API tests

- [x] list `include_deleted`；`get` 过滤已软删；`get_including_deleted`；soft_delete；restore；hard_delete
- [x] CallRecordRepository：`exists_for_customer_service`
- [x] routes：DELETE / restore / purge；注入 call_records
- [x] pytest（软删、恢复、purge 409/204）

### Task 3: Web API + UI + tests

- [x] RealtimeVoiceService：include_deleted / delete / restore / purge
- [x] assistant-settings 列表：显示已删除、软删、恢复、完全删除
- [x] vitest

### Task 4: 本地验证

- [x] API + Web 相关测试通过
- [x] Stage1 部署仅在用户另授后做
