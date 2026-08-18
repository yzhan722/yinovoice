# Appointments + Callbacks Phase 1 Implementation Plan

> **For agentic workers:** Use task-by-task execution. Steps use checkbox syntax.

**Goal:** 预约/回拨真实 CRUD（网页可用），Stage1 可验收。

**Architecture:** 新表 + InMemory/Postgres repo + FastAPI routes；前端服务改打真 API。

**Tech Stack:** FastAPI, Alembic, SQLAlchemy, Vue 3, Pytest, Vitest

## Global Constraints

- Spec: `docs/platform/superpowers/specs/2026-08-17-appointments-callbacks-phase1-design.md`
- 不上生产；不自动 commit；先本地测试

---

### Task 1: Domain + migration + ORM

- [x] domain `appointment.py` / `callback_task.py`
- [x] Alembic `20260817_0004`
- [x] SQLAlchemy models

### Task 2: Repos + routes + wire app

- [x] InMemory + Postgres
- [x] routers + `create_app` include
- [x] pytest

### Task 3: Web

- [x] Realtime/platform services 真 API
- [x] appointments / callback-tasks 页面
- [x] vitest 更新

### Task 4: 验证

- [x] 本地测试通过
- [x] Stage1 另授
