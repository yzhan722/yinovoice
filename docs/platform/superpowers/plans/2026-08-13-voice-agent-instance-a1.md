# Voice Agent Instance A1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tenant-scoped, PostgreSQL-backed Voice Agent Instance list/select/detail/edit flow and remove fixed Demo Instance selection from active user flows.

**Architecture:** Extend the existing CustomerServiceRepository seam with a paginated tenant list operation and expose it through the existing FastAPI router. Keep RealtimeVoiceService as the Platform API client and add a small selection module that resolves route, session, and first-list-item choices without leaking legacy numeric `attId` into the new flow.

**Tech Stack:** Python 3.11–3.14, FastAPI, Pydantic, SQLAlchemy async, PostgreSQL, Vue 3, TypeScript, Vitest.

## Global Constraints

- Work only in `E:\Repos\yinovoice`.
- Do not delete files or modify unrelated business behavior.
- Do not commit, push, create a PR, deploy, or modify remote settings.
- Preserve tenant isolation through `X-Tenant-ID`.
- Use UUID strings for the new instance flow.
- Write a failing test before every production behavior.

---

### Task 1: Tenant-scoped instance repository listing

**Files:**
- Modify: `apps/control-plane/api/src/yino_platform_api/repositories/customer_services.py`
- Modify: `apps/control-plane/api/src/yino_platform_api/repositories/postgres/customer_services.py`
- Test: `apps/control-plane/api/tests/test_postgres_customer_service_repository.py`

**Interfaces:**
- Produces: `list_for_tenant(tenant_id: UUID, *, limit: int, offset: int) -> tuple[list[CustomerServiceInstance], int]`

- [ ] Add failing in-memory and PostgreSQL tests for tenant filtering, pagination and total.
- [ ] Run focused tests and confirm failure because `list_for_tenant` is missing.
- [ ] Add the protocol, in-memory and PostgreSQL implementations with `updated_at DESC, id DESC` ordering.
- [ ] Re-run focused tests.

### Task 2: Customer Service list HTTP endpoint

**Files:**
- Modify: `apps/control-plane/api/src/yino_platform_api/routes/customer_services.py`
- Test: `apps/control-plane/api/tests/test_customer_service_api.py`

**Interfaces:**
- Produces: `GET /api/v1/customer-services?limit=&offset=` returning `{items, total}`.

- [ ] Add failing API tests for paging, validation and tenant isolation.
- [ ] Run focused tests and confirm 404/405 or response mismatch.
- [ ] Add `CustomerServicePage` and the collection route before `/{instance_id}`.
- [ ] Re-run API tests.

### Task 3: Platform client and selection module

**Files:**
- Modify: `apps/control-plane/web/src/api/platform/RealtimeVoiceService.ts`
- Create: `apps/control-plane/web/src/api/platform/instanceSelection.ts`
- Test: `apps/control-plane/web/src/api/platform/RealtimeVoiceService.test.ts`
- Create: `apps/control-plane/web/src/api/platform/instanceSelection.test.ts`

**Interfaces:**
- Produces: `listCustomerServices(page, signal)` and pure `resolveInstanceSelection()` behavior.

- [ ] Add failing tests for the collection request, UUID preservation and selection precedence.
- [ ] Run focused Vitest files and confirm expected failures.
- [ ] Implement the minimal client and pure selection helpers.
- [ ] Re-run focused tests and typecheck.

### Task 4: Connect instance list and active pages

**Files:**
- Modify: `apps/control-plane/web/src/pages/user/assistant-settings/index.vue`
- Modify: `apps/control-plane/web/src/pages/user/realtime-voice/index.vue`
- Modify: `apps/control-plane/web/src/pages/user/knowledge-base/index.vue`
- Test: related page tests under `apps/control-plane/web/src/pages/user/`

**Interfaces:**
- Consumes: real instance page and selection helper from Task 3.

- [ ] Add failing component tests showing list rendering and selected UUID propagation.
- [ ] Run focused tests and confirm fixed Demo behavior fails the assertions.
- [ ] Replace mock/legacy calls in these active tenant pages with RealtimeVoiceService and current selection.
- [ ] Re-run focused tests.

### Task 5: Validation and project state

**Files:**
- Modify: `README.md`
- Modify: `PROJECT_STATUS.md`
- Modify: `TASKS.md`

- [ ] Run API tests in a compliant Python environment; report missing dependencies instead of substituting Python 3.10.
- [ ] Run `pnpm test`, `pnpm typecheck`, and `pnpm build`.
- [ ] Run `git diff --check`, sensitive-file checks and inspect changed paths.
- [ ] Update status and task documents with actual evidence only.
- [ ] Leave all changes unstaged and uncommitted for GitHub Desktop review.
