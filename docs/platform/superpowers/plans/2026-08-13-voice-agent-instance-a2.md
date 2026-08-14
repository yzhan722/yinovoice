# Voice Agent Instance A2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tenant-scoped voice-agent instance creation to the API and Web, plus a guarded, idempotent synthetic-demo seeder.

**Architecture:** A dedicated create request model constructs a server-owned `CustomerServiceInstance` and persists it through an explicit repository create operation. The existing instance list page owns a focused creation dialog and delegates HTTP calls to `RealtimeVoiceService`. A separate seed module contains synthetic definitions and refuses execution unless an explicit safe environment is supplied.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, SQLAlchemy async, pytest, Vue 3, TypeScript, TDesign, Vitest, pnpm.

## Global Constraints

- Do not delete files or data.
- Do not read, print, or write real credentials or connection strings.
- Do not write to an unknown or production database.
- Do not commit, push, create a PR, or deploy automatically.
- All demo content must be synthetic and contain no real customer, patient, contact, recording, or address data.
- Production behavior must be introduced through a failing test first.

---

### Task 1: Domain create contract and repository behavior

**Files:**
- Modify: `apps/control-plane/api/src/yino_platform_api/domain/customer_service.py`
- Modify: `apps/control-plane/api/src/yino_platform_api/repositories/customer_services.py`
- Modify: `apps/control-plane/api/src/yino_platform_api/repositories/postgres/customer_services.py`
- Test: `apps/control-plane/api/tests/test_customer_service_domain.py`

**Interfaces:**
- Produces: `CustomerServiceCreate` with permitted user fields and safe defaults.
- Produces: `CustomerServiceRepository.create(instance) -> CustomerServiceInstance`.
- Produces: `CustomerServiceAlreadyExists` conflict.

- [ ] Write tests proving safe defaults, forbidden server-owned fields, successful create, duplicate rejection, and tenant-scoped retrieval.
- [ ] Run focused tests and confirm failures are caused by missing A2 contracts.
- [ ] Add the minimal domain model and in-memory/PostgreSQL repository implementations.
- [ ] Run focused tests until green, then run Ruff on changed backend files.

### Task 2: POST customer-services API

**Files:**
- Modify: `apps/control-plane/api/src/yino_platform_api/routes/customer_services.py`
- Test: `apps/control-plane/api/tests/test_customer_service_api.py`

**Interfaces:**
- Consumes: `CustomerServiceCreate`, repository `create`.
- Produces: `POST /api/v1/customer-services` returning `201 CustomerServiceInstance`.

- [ ] Write tests for 201 creation, server UUID/current tenant/version 1, subsequent list/detail retrieval, forbidden `id`/`tenant_id`/`version`, and validation errors.
- [ ] Run focused API tests and confirm expected 404/405 failures.
- [ ] Implement server-side construction with `uuid4`, current tenant, version 1, and explicit 409 mapping.
- [ ] Run focused and full API tests.

### Task 3: Web API client

**Files:**
- Modify: `apps/control-plane/web/src/api/platform/RealtimeVoiceService.ts`
- Test: `apps/control-plane/web/src/api/platform/RealtimeVoiceService.test.ts`

**Interfaces:**
- Produces: `CustomerServiceCreateInput`.
- Produces: `createCustomerService(input) -> Promise<CustomerServiceInstance>`.

- [ ] Write a failing request-shape test that asserts POST path/body.
- [ ] Run the focused test and confirm the method is missing.
- [ ] Implement the minimal typed client method.
- [ ] Run focused client tests.

### Task 4: Instance creation dialog and truthful list states

**Files:**
- Create: `apps/control-plane/web/src/pages/user/assistant-settings/InstanceCreateDialog.vue`
- Create: `apps/control-plane/web/src/pages/user/assistant-settings/InstanceCreateDialog.test.ts`
- Modify: `apps/control-plane/web/src/pages/user/assistant-settings/index.vue`
- Modify: `apps/control-plane/web/src/pages/user/assistant-settings/index.test.ts`

**Interfaces:**
- Dialog emits `created(instance: CustomerServiceInstance)` after successful creation.
- Page saves returned UUID and routes to `KnowledgeBaseIndex?instanceId=<uuid>`.

- [ ] Write failing tests for opening, required fields, correct submit input, preserved input/error on failure, disabled duplicate submit, success emit, list load error, and successful navigation.
- [ ] Run focused tests and confirm failures arise from missing UI behavior.
- [ ] Implement the smallest focused dialog and integrate it into the list page.
- [ ] Run focused page/dialog tests, then Web full tests and typecheck.

### Task 5: Guarded idempotent synthetic demo seed

**Files:**
- Create: `apps/control-plane/api/src/yino_platform_api/demo_seed.py`
- Create: `apps/control-plane/api/tests/test_demo_seed.py`
- Modify only if required for an existing documented CLI entry: `apps/control-plane/api/pyproject.toml`

**Interfaces:**
- Produces: `seed_demo_instances(repository, tenant_id, environment, allow_demo_seed) -> SeedResult`.
- `environment` accepts only `local` or `test`; `allow_demo_seed` must be true.
- Produces four deterministic synthetic instances and skips existing IDs.

- [ ] Write failing tests for environment refusal, four-instance creation, repeat-run skips, and isolation from unrelated tenant data.
- [ ] Run focused tests and confirm the seed function is missing.
- [ ] Implement pure synthetic definitions and guarded idempotent seeding without reading environment files or printing secrets.
- [ ] Run focused and full API tests.
- [ ] Do not execute against a database unless its local/test identity is independently established.

### Task 6: Documentation and final verification

**Files:**
- Modify: `PROJECT_STATUS.md`
- Modify: `TASKS.md`
- Modify: `README.md` only if a safe documented seed command is added.

- [ ] Record A2 truthfully, distinguishing implemented UI/API from any seed execution not performed.
- [ ] Run API full tests and changed-file Ruff.
- [ ] Run Web full tests, typecheck, and production build.
- [ ] Run `git diff --check`, conflict checks, `git status`, branch, and remote checks.
- [ ] Review the diff for credentials, real customer/contact/medical/recording data, generated artifacts, and unintended business changes.
- [ ] Leave all changes uncommitted for user review in GitHub Desktop.
