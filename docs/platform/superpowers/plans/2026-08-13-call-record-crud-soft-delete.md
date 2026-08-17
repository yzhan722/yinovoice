# 通话记录 CRUD（软删除）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为通话记录补齐 PUT / 软删除 DELETE / restore，并在 Stage1 网页可操作。

**Architecture:** `call_records.deleted_at` 软删除；列表默认过滤；详情对已删返回 404；InMemory 与 Postgres 双实现；前端列表删除、详情编辑保存。

**Tech Stack:** FastAPI, Alembic, SQLAlchemy, Vue 3, Vitest, Pytest

## Global Constraints

- 规格：`docs/platform/superpowers/specs/2026-08-13-call-record-crud-soft-delete-design.md`
- 主仓库：`E:\Repos\yinovoice`
- 先 Stage1；不上生产；不自动 commit

---

### Task 1: Domain + migration + models

- [ ] `CallRecord.deleted_at`、`CallRecordUpdate`
- [ ] Alembic `20260813_0002_...`
- [ ] `CallRecordRow.deleted_at`

### Task 2: Repositories + routes + API tests

- [ ] list `include_deleted`；soft_delete；restore；PUT
- [ ] CORS 允许 DELETE
- [ ] pytest

### Task 3: Web API + UI + tests

- [ ] RealtimeVoiceService / TenantCallRecordService 方法
- [ ] 列表删除、详情编辑保存与删除
- [ ] vitest

### Task 4: Stage1 迁移与部署验证

- [ ] stage1 DB alembic upgrade
- [ ] 重新部署 stage1 API/web
- [ ] 冒烟：改/删/恢复
