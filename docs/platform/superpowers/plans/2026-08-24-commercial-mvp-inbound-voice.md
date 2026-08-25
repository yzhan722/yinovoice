# 商业 MVP 入站电话闭环实施计划

> **For agentic workers:** 按里程碑推进。步骤用 checkbox。未经用户明确授权不得 commit / push / 部署。

**Goal:** 把当前网页 LiveKit + Qwen Demo 推进到可试点的入站电话闭环（号码映射 → 通话生命周期 → 排期/Tool → 录音/通知 → 运营页）。

**Architecture:** 复用 `apps/control-plane/api` 的 FastAPI Repository + Alembic，`apps/runtime/voice-agent` 的 DispatchMetadata / Qwen Realtime，`apps/control-plane/web` 的 TDesign 租户页。不扩展 `deploy/src`。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy async、Alembic、pytest、LiveKit Agents、Vue 3、TDesign、Vitest。

## Global Constraints

- Yino 是业务与配置唯一事实来源；Vapi/n8n 不进实时通话。
- 不读不写真实密钥；新变量只进 `.env.example`。
- 继续 `X-Tenant-ID` Demo 租户头。
- TDD：先失败测试，再最小实现。
- SIP 入站落库 `direction=inbound`；metadata `channel=sip`。
- Alembic 下一 revision：`20260824_0005`，revises `20260817_0004`。
- 不 commit，除非用户另行授权。

## 基线（原本失败，勿当回归）

- API：`test_create_app_defaults_to_memory_without_database_url`（`.env.local` 仍提供 `DATABASE_URL`）
- API：预约/回拨/demo/purge 四测在未 migrate 的 Postgres 上 `UndefinedTable` / 缺列
- voice-agent：6 个既有 Qwen Realtime 测试失败
- web：本机 `pnpm` 不在 PATH

---

### Task 1: E.164 与 PhoneNumber 领域

**Files:**

- Create: `apps/control-plane/api/src/yino_platform_api/domain/phone_number.py`
- Test: `apps/control-plane/api/tests/test_phone_number_domain.py`

**Interfaces:**

- Produces: `normalize_e164(value: str) -> str`；`PhoneNumber` / `PhoneNumberCreate` / `PhoneNumberUpdate`；`PhoneNumberLookup`

- [ ] **Step 1: 写失败测试**（非法号码、合法压缩、跨租户字段 forbid）
- [ ] **Step 2: 最小实现使测试通过**
- [ ] **Step 3: 运行** `.\.venv\Scripts\python.exe -m pytest tests/test_phone_number_domain.py -q`

---

### Task 2: 内存仓库 + HTTP API

**Files:**

- Create: `repositories/phone_numbers.py`（Protocol + InMemory + `PhoneNumberConflict`）
- Create: `routes/phone_numbers.py`
- Modify: `app.py` 注入仓库与路由
- Modify: `tests/test_app_repository_wiring.py` 显式仓库列表加上 phone numbers
- Test: `tests/test_phone_number_api.py`

**Interfaces:**

- Consumes: Task 1 领域类型；`CustomerServiceRepository.get`
- Produces: `/api/v1/phone-numbers` CRUD + `/lookup`

- [ ] **Step 1: API 测试先红**（创建、lookup、重复 409、跨租户 404、旧实例软删拒绝、禁用后 lookup 404）
- [ ] **Step 2: 实现 InMemory + routes + create_app 接线**
- [ ] **Step 3: pytest 目标文件 + 既有 `tests/test_livekit_tokens.py` 确认网页 dispatch 未改**

---

### Task 3: ORM + Alembic + Postgres adapter

**Files:**

- Modify: `db/models.py` 增加 `PhoneNumberRow`
- Create: `migrations/versions/20260824_0005_phone_numbers.py`
- Create: `repositories/postgres/phone_numbers.py`
- Modify: `repositories/postgres/__init__.py`
- Test: `tests/test_postgres_phone_number_repository.py`（`DATABASE_URL` skipif）

- [ ] **Step 1: 迁移与 adapter 测试**
- [ ] **Step 2: create_app 在 postgres 模式下接线**
- [ ] **Step 3: ruff 只检查新文件**

---

### Task 4: DispatchMetadata 可选 SIP 字段

**Files:**

- Modify: `apps/runtime/voice-agent/src/yino_voice_agent/runtime_config.py`
- Modify: `apps/runtime/voice-agent/tests/test_runtime_config.py`
- Modify: `apps/control-plane/api/src/yino_platform_api/services/livekit_tokens.py` 保持三字段网页 JSON

- [ ] **Step 1: 测试旧三字段、SIP 全字段、未知键拒绝、重复 key 拒绝**
- [ ] **Step 2: `from_json` 传入 optional_keys（辅助函数已支持）**
- [ ] **Step 3: `pytest tests/test_runtime_config.py tests/test_server.py -q`**

---

### Task 5: LiveKit SIP dry-run 生成器

**Files:**

- Create: `apps/control-plane/api/src/yino_platform_api/services/livekit_sip.py`
- Create: `scripts/provision_livekit_sip.py`
- Test: `apps/control-plane/api/tests/test_livekit_sip_provision.py`

- [ ] **Step 1: 快照测试生成的 trunk/rule/metadata（无密钥）**
- [ ] **Step 2: CLI `--dry-run` 打印 JSON**
- [ ] **Step 3: 运行目标测试；不调用网络**

---

## 后续里程碑文件地图（实现时再拆 TDD 步骤）

**M2** `routes/call_sessions.py`、`services/call_lifecycle.py`、`domain/call_record.py` 放宽 in_progress、Runtime `call_lifecycle.py` + `server.py`。

**M3** `domain/scheduling.py`、`services/availability.py`、`routes/scheduling.py`、改 `intent_extract.py`。

**M4** `domain/tool_invocation.py`、`services/tool_execution.py`、`routes/tool_invocations.py`。

**M5** Runtime `tool_protocol.py`、`tool_client.py`、`tool_orchestrator.py`；prompt；剥标记后再 TTS。

**M6** `services/livekit_egress.py`、call_record 录音字段、presign。

**M7** `domain/notification.py`、`services/notifications.py`、SMTP Fake。

**M8** `permission.ts` 菜单；`pages/user/telephony`；`pages/user/scheduling`；`CallRecordDetailDrawer.vue`；Dashboard API。

**M9** `.env.example`、合成冒烟、`TASKS.md` / `PROJECT_STATUS.md` / `DECISIONS.md` 与代码对齐。

---

## Milestone 1 精确改动清单

创建：

- `apps/control-plane/api/src/yino_platform_api/domain/phone_number.py`
- `apps/control-plane/api/src/yino_platform_api/repositories/phone_numbers.py`
- `apps/control-plane/api/src/yino_platform_api/repositories/postgres/phone_numbers.py`
- `apps/control-plane/api/src/yino_platform_api/routes/phone_numbers.py`
- `apps/control-plane/api/src/yino_platform_api/services/livekit_sip.py`
- `apps/control-plane/api/migrations/versions/20260824_0005_phone_numbers.py`
- `apps/control-plane/api/tests/test_phone_number_domain.py`
- `apps/control-plane/api/tests/test_phone_number_api.py`
- `apps/control-plane/api/tests/test_livekit_sip_provision.py`
- `apps/control-plane/api/tests/test_postgres_phone_number_repository.py`
- `scripts/provision_livekit_sip.py`

修改：

- `apps/control-plane/api/src/yino_platform_api/app.py`
- `apps/control-plane/api/src/yino_platform_api/db/models.py`
- `apps/control-plane/api/src/yino_platform_api/repositories/postgres/__init__.py`
- `apps/control-plane/api/tests/test_app_repository_wiring.py`
- `apps/runtime/voice-agent/src/yino_voice_agent/runtime_config.py`
- `apps/runtime/voice-agent/tests/test_runtime_config.py`
