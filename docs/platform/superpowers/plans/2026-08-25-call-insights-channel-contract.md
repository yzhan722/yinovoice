# 通话后报告层对接自家语音 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Insights 增加渠道无关的挂断入站；Yino 仅在助手被手动绑定后异步投递对话；默认不发报告邮件。

**Architecture:** 两个仓库继续独立。Insights 保留 `POST /v1/vapi/:profile`。新增 `POST /v1/ingest/:profile` 把规范 JSON 变成现有 `Call` + 分析作业。`channel=yino` 的通话默认不进邮件 outbox，除非该 profile 显式 `mailEnabled: true`。Yino 在实例上增加可空 `insights_profile`；挂断成功后入队，HTTP 失败不回滚通话。

**Tech Stack:** Insights：TypeScript、Fastify、Zod、better-sqlite（`node:sqlite`）、Vitest。Yino：Python 3.12、Pydantic、FastAPI、SQLAlchemy、Alembic、pytest。

## Global Constraints

- 不合并 git 仓库；不改 LucaPlus / INP 的 VAPI Server URL。
- 不发送额外客户邮件；`channel=yino` 默认不建 mail outbox。
- 不把录音文件或内部 S3 地址送进 Insights（`recordingUrl` 第一期为 `null`）。
- 不自动创建 Insights 客户；未知 slug → 404。
- Yino 挂断 HTTP 必须在 Insights 失败时仍成功。
- 不读不写真实密钥；新变量只进 `.env.example`。
- TDD：先失败测试，再最小实现。
- 未经用户明确授权不得 commit / push / 部署。Yino Alembic 下一 revision：`20260825_0010`，revises `20260824_0009`。

## 文件地图

**Insights**（`C:\Users\yino\Projects\n8n-workflow-export\apps\vapi-call-insights`）

| 路径 | 职责 |
|------|------|
| `src/domain/schemas.ts` | `EndedCallIngestSchema`、`mailEnabled` 可选 |
| `src/domain/types.ts` | `Call.channel`、`ClientProfile.mailEnabled` |
| `src/application/normalize-ended-call.ts` | Yino/规范体 → `NormalizedEvent` |
| `src/api/app.ts` | `POST /v1/ingest/:profile` |
| `src/config.ts` / `src/api/server.ts` | `INGEST_AUTH_TOKEN` |
| `src/storage/sqlite-store.ts` | `calls.channel` 列与读写 |
| `src/outbound/outbox-planner.ts` | yino 渠道默认不入队邮件 |
| `src/application/normalize-vapi-event.ts` | VAPI 进线标 `channel: "vapi"` |
| `deploy/vapi-call-insights.env.example` | 文档化 ingest token |

**Yino**（`C:\Users\yino\Projects\yinovoice`）

| 路径 | 职责 |
|------|------|
| `apps/control-plane/api/src/yino_platform_api/domain/customer_service.py` | `insights_profile` |
| `apps/control-plane/api/src/yino_platform_api/domain/insights_dispatch.py` | 纯函数：转写、eventId、JSON 体 |
| `apps/control-plane/api/migrations/versions/20260825_0010_insights_profile_dispatch.py` | 列 + 队列表 |
| `apps/control-plane/api/src/yino_platform_api/services/insights_dispatch.py` | 入队 + 投递 |
| `apps/control-plane/api/src/yino_platform_api/services/call_lifecycle.py` | `finish` 后入队 |
| `apps/control-plane/api/src/yino_platform_api/config.py` | `insights_base_url` / `insights_ingest_token` |
| `apps/control-plane/api/.env.example` | 新变量名 |

第一期不做 Vue 表单；用现有 customer-service PUT 写 `insights_profile`。

---

### Task 1: Insights 规范挂断体 → NormalizedEvent

**Files:**

- Create: `C:\Users\yino\Projects\n8n-workflow-export\apps\vapi-call-insights\src\application\normalize-ended-call.ts`
- Modify: `C:\Users\yino\Projects\n8n-workflow-export\apps\vapi-call-insights\src\domain\schemas.ts`
- Modify: `C:\Users\yino\Projects\n8n-workflow-export\apps\vapi-call-insights\src\domain\types.ts`（`Call` 增加 `channel: "vapi" | "yino"`）
- Test: `C:\Users\yino\Projects\n8n-workflow-export\apps\vapi-call-insights\test\normalize-ended-call.test.ts`

**Interfaces:**

- Produces: `EndedCallIngestSchema`；`normalizeEndedCall(profile: ClientProfile, body: unknown, now: Date): NormalizedEvent`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";
import { normalizeEndedCall } from "../src/application/normalize-ended-call.js";
import { lucaplusProfile } from "./fixtures.js";

const body = {
  schemaVersion: 1,
  channel: "yino",
  callId: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  eventId: "a".repeat(64),
  startedAt: "2026-08-25T03:00:00.000Z",
  endedAt: "2026-08-25T03:04:12.000Z",
  durationSeconds: 252,
  transcript: "user: hello\nassistant: hi",
  summary: "",
  recordingUrl: null,
};

describe("normalizeEndedCall", () => {
  it("accepts a yino ended-call and queues analysis", () => {
    const event = normalizeEndedCall(
      lucaplusProfile,
      body,
      new Date("2026-08-25T03:05:00.000Z"),
    );
    expect(event.action).toBe("analyze");
    expect(event.call?.channel).toBe("yino");
    expect(event.call?.callId).toBe(body.callId);
    expect(event.call?.recordingUrl).toBeNull();
    expect(event.eventId).toBe(body.eventId);
  });

  it("rejects extra keys, missing transcript+summary, and non-UTC timestamps", () => {
    expect(() =>
      normalizeEndedCall(lucaplusProfile, { ...body, extra: true }, new Date()),
    ).toThrow();
    expect(() =>
      normalizeEndedCall(
        lucaplusProfile,
        { ...body, transcript: "", summary: "" },
        new Date(),
      ),
    ).toThrow();
    expect(() =>
      normalizeEndedCall(
        lucaplusProfile,
        { ...body, startedAt: "2026-08-25T03:00:00+00:00" },
        new Date(),
      ),
    ).toThrow();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:\Users\yino\Projects\n8n-workflow-export\apps\vapi-call-insights && npm test -- test/normalize-ended-call.test.ts`
Expected: FAIL（模块不存在）

- [ ] **Step 3: Write minimal implementation**

`EndedCallIngestSchema`：`z.object({...}).strict()`。时间戳正则与 mail cutover 相同：`/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/`。`callId` 复用 `ArtifactPathSegmentSchema`。`eventId` 为 64 位 hex。`durationSeconds` 整数 0–86400，且必须等于 `floor((ended-start)/1000)`。`recordingUrl` 只允许 `null`。`channel` 只允许 `"yino"`（本入口不收 vapi 体）。`payloadHash` 对校验后的对象做稳定 JSON SHA-256。`event.eventId` 用请求里的 `eventId`（Yino 负责去重键）。

`Call.channel` 改为必填：`"vapi" | "yino"`。随后 Task 3 会改 VAPI normalizer 一律写 `"vapi"`；本任务先改 `types.ts` 与 `makeCall` 默认 `channel: "vapi"`，并修编译。

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- test/normalize-ended-call.test.ts`
Expected: PASS；若 `tsc` 因 `makeCall` 缺字段失败，在本任务一并补默认 `channel: "vapi"`。

---

### Task 2: `POST /v1/ingest/:profile` + 独立 Bearer

**Files:**

- Modify: `src/api/app.ts`（`ingestAuth?: WebhookAuthConfig`；新路由）
- Modify: `src/config.ts`（`ingestAuthToken: string | null`，来自 `INGEST_AUTH_TOKEN`）
- Modify: `src/api/server.ts`（把 ingest token 注入 `buildApp`）
- Modify: `deploy/vapi-call-insights.env.example`
- Test: `test/api.test.ts`（新 `describe("yino ingest")`）
- Test: 现有 `createApiHarness` 增加可选 `ingestAuth`

**Interfaces:**

- Consumes: Task 1 `normalizeEndedCall`
- Produces: `POST /v1/ingest/:profile` → 与 VAPI 路由相同的 `{ status, callId, jobId }`；202 accepted / 200 duplicate

- [ ] **Step 1: Write the failing test**

在 `test/api.test.ts` 增加：

```ts
describe("yino ingest", () => {
  it("accepts a bound profile with ingest bearer and does not use the vapi webhook token", async () => {
    const harness = createApiHarness({
      ingestAuth: { required: true, token: "ingest-test-token-32-chars-minimum" },
      webhookAuth: { required: true, token: "vapi-webhook-token-32-chars-minimum" },
    });
    const ended = { /* Task 1 合法体 */ };
    const denied = await harness.app.inject({
      method: "POST",
      url: "/v1/ingest/lucaplus",
      headers: { authorization: "Bearer vapi-webhook-token-32-chars-minimum" },
      payload: ended,
    });
    expect(denied.statusCode).toBe(401);

    const ok = await harness.app.inject({
      method: "POST",
      url: "/v1/ingest/lucaplus",
      headers: { authorization: "Bearer ingest-test-token-32-chars-minimum" },
      payload: ended,
    });
    expect(ok.statusCode).toBe(202);
    expect(ok.json().status).toBe("accepted");
    await harness.close();
  });

  it("returns 404 for unknown profile and 400 for empty transcript", async () => {
    // inject 未知 slug → 404
    // 合法鉴权 + transcript/summary 皆空 → 400，store.getCall 为 null
  });
});
```

保留并跑现有 lucaplus / inp-group webhook 用例（本文件后半段不要删）。

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- test/api.test.ts`
Expected: FAIL（无 `/v1/ingest`）

- [ ] **Step 3: Write minimal implementation**

`isAuthorizedWebhook` 复用于 ingest，配置对象分开。未知 profile 404。`normalizeEndedCall` 抛错 → 400。`ingestion.ingest` 后 202/200 规则与 `/v1/vapi/:profile` 相同。生产环境：**不要**因为缺少 `INGEST_AUTH_TOKEN` 让整个 API 起不来；token 为空时 ingest 一律 401，VAPI webhook 不受影响。

- [ ] **Step 4: Run tests**

Run: `npm test -- test/api.test.ts`
Expected: PASS，包括原 VAPI 用例。

---

### Task 3: 持久化 channel；yino 默认不建邮件 outbox

**Files:**

- Modify: `src/storage/sqlite-store.ts`（SCHEMA 增加 `channel TEXT NOT NULL DEFAULT 'vapi'`；对已有库 `PRAGMA table_info` 后 `ALTER TABLE`；INSERT/getCall）
- Modify: `src/application/normalize-vapi-event.ts`（`call.channel = "vapi"`）
- Modify: `src/outbound/outbox-planner.ts`
- Modify: `src/domain/schemas.ts` / `types.ts` / `src/profiles/runtime-config.ts` 校验：`mailEnabled` 可选 boolean
- Modify: `src/profiles/lucaplus.json` 与 `inp-group.json`：**不要**加 `mailEnabled`（缺省视为仅对 vapi 渠道发信）
- Test: `test/outbox-planner.test.ts`
- Test: `test/sqlite-store.test.ts`（若有 getCall 断言则补 channel）

**Interfaces:**

- Produces: `OutboxPlanner.plan` 在 `input.call.channel === "yino" && input.profile.mailEnabled !== true` 时直接 return（零 mail 行）
- VAPI 通话 `channel === "vapi"`：行为与今天完全相同（off/shadow/live+cutover）

- [ ] **Step 1: Write the failing test**

```ts
it("does not enqueue mail for yino channel unless mailEnabled is true", () => {
  const store = new SqliteStore(tempDatabase().path);
  const planner = new OutboxPlanner(store, { mode: "shadow", cutoverNotBefore: null });
  planner.plan(makeCompletedReportInput({
    call: makeCall({ channel: "yino", callId: "yino_call_1" }),
  }));
  expect(store.listMail("lucaplus", "yino_call_1")).toEqual([]);

  planner.plan(makeCompletedReportInput({
    profile: { ...lucaplusProfile, mailEnabled: true },
    call: makeCall({ channel: "yino", callId: "yino_call_2" }),
  }));
  expect(store.listMail("lucaplus", "yino_call_2")).toHaveLength(2);
});

it("still enqueues vapi lucaplus mail without mailEnabled", () => {
  // 现有 shadow 用例必须继续：makeCall 默认 channel vapi，listMail 两条 suppressed
});
```

`makeCompletedReportInput` 若把 `call` 整对象传入，按现有 helper 改签名（读 `test/outbox-planner.test.ts` 底部 helper，增加 `call` 覆盖）。

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- test/outbox-planner.test.ts`
Expected: FAIL（yino 仍入队）

- [ ] **Step 3: Write minimal implementation**

Planner 开头：

```ts
if (input.call.channel === "yino" && input.profile.mailEnabled !== true) {
  return;
}
```

SQLite：新库 SCHEMA 含 `channel`；旧库构造函数在 `exec(SCHEMA)` 之后：

```ts
const cols = this.db.prepare("PRAGMA table_info(calls)").all() as Array<{ name: string }>;
if (!cols.some((col) => col.name === "channel")) {
  this.db.exec("ALTER TABLE calls ADD COLUMN channel TEXT NOT NULL DEFAULT 'vapi'");
}
```

`ClientProfileSchema` 增加 `mailEnabled: z.boolean().optional()`。runtime 加载必须允许该字段。

- [ ] **Step 4: Run tests**

Run: `npm test && npx tsc --noEmit`
Expected: 全绿。

---

### Task 4: Yino `insights_profile` 领域与 API

**Files:**

- Modify: `apps/control-plane/api/src/yino_platform_api/domain/customer_service.py`
- Modify: `apps/control-plane/api/src/yino_platform_api/repositories/postgres/customer_services.py`（`_to_domain` / insert / update）
- Modify: InMemory customer service 映射（若手写 dict）
- Test: `apps/control-plane/api/tests/test_customer_service_domain.py`（若无则新建）或现有 instance 测试文件
- Test: 扩一个现有 customer-service API 测试：PUT 写入 slug，GET 读回；默认 demo 为 `null`

**Interfaces:**

- Produces: `CustomerServiceInstance.insights_profile: str | None = None`  
  校验：`None` 或匹配 `^[A-Za-z0-9._-]{1,64}$`，且不是 `.` / `..`。空串 normalize 成 `None`。

- [ ] **Step 1: Write the failing test**

```python
def test_insights_profile_optional_and_rejects_bad_slug() -> None:
    demo = CustomerServiceInstance.demo(instance_id=..., tenant_id=...)
    assert demo.insights_profile is None
    CustomerServiceInstance.demo(...).model_copy(update={"insights_profile": "inp-group"})
    with pytest.raises(ValidationError):
        CustomerServiceInstance.demo(...).model_copy(update={"insights_profile": "bad slug"})
```

- [ ] **Step 2: Run** `.\.venv\Scripts\python.exe -m pytest tests/test_customer_service_domain.py -q`（或你放测试的文件）  
  Expected: FAIL

- [ ] **Step 3: 最小实现字段 + Create/Update 可选**  
  `extra=forbid` 保持。旧客户端不传该字段 → `None`。

- [ ] **Step 4: pytest 目标文件 PASS**；再跑相关 API 测试确认列表/详情 JSON 含 `"insights_profile": null`。

---

### Task 5: Alembic 0010 — 实例列 + 投递队列表

**Files:**

- Create: `apps/control-plane/api/migrations/versions/20260825_0010_insights_profile_dispatch.py`
- Modify: `apps/control-plane/api/src/yino_platform_api/db/models.py`
- Create: `apps/control-plane/api/src/yino_platform_api/repositories/insights_dispatch.py`（Protocol + InMemory）
- Create: `apps/control-plane/api/src/yino_platform_api/repositories/postgres/insights_dispatch.py`
- Modify: `repositories/postgres/__init__.py`
- Test: `tests/test_postgres_insights_dispatch_repository.py`（`DATABASE_URL` skipif）
- Test: InMemory 入队/按 next_attempt 领取 放 `tests/test_insights_dispatch_memory.py`

**Interfaces:**

- Produces:

```python
class InsightsDispatchJob(BaseModel):
    id: UUID
    tenant_id: UUID
    call_id: UUID
    profile: str
    event_id: str
    body: dict[str, object]  # 已是规范 JSON
    status: Literal["pending", "sent", "failed"]
    attempts: int
    next_attempt_at: datetime | None
    last_error: str = ""
```

`enqueue(job) -> InsightsDispatchJob`：同一 `call_id` 已存在则返回已有行（幂等）。  
`claim_due(now) -> InsightsDispatchJob | None`  
`mark_sent(id)` / `mark_retry(id, error, next_attempt_at)` / `mark_failed(id, error)`（4xx 永久失败）

表 `insights_dispatch_jobs`：`call_id` UNIQUE；status check 如上。  
`voice_agent_instances.insights_profile` TEXT NULL。

- [ ] **Step 1: 内存仓库测试先红**（enqueue 两次同 call_id 只有一行；claim 只取 `pending` 且 `next_attempt_at` 空或已到期）
- [ ] **Step 2: 实现 InMemory + ORM + Alembic `upgrade`/`downgrade`**
- [ ] **Step 3:** `pytest tests/test_insights_dispatch_memory.py -q`；有 `DATABASE_URL` 再跑 postgres 测试

---

### Task 6: 规范 JSON 纯函数

**Files:**

- Create: `apps/control-plane/api/src/yino_platform_api/domain/insights_dispatch.py`
- Test: `apps/control-plane/api/tests/test_insights_payload.py`

**Interfaces:**

- Produces:

```python
def format_utc_ms(value: datetime) -> str: ...
def build_event_id(profile: str, call_id: UUID, ended_at: datetime) -> str: ...
def format_transcript(messages: list[TranscriptMessage]) -> str: ...
def build_ended_call_body(*, profile: str, record: CallRecord) -> dict[str, object]: ...
```

`format_transcript`：按 `sequence` 排序，每行 `user: {text}` 或 `assistant: {text}`（Yino role 已是 `user`/`assistant`），`\n` 连接。  
`build_event_id`：`sha256(f"yino|{profile}|{call_id}|{format_utc_ms(ended_at)}".encode()).hexdigest()`  
`build_ended_call_body`：`recordingUrl` 恒为 `None`；`summary` 恒为 `""`；无消息则 `transcript==""`（调用方不得入队）。

- [ ] **Step 1: 写失败测试**（固定 datetime → 固定 eventId 与 JSON 字段；乱序 sequence 仍按号排序）
- [ ] **Step 2: pytest 红**
- [ ] **Step 3: 实现**
- [ ] **Step 4: pytest 绿**

---

### Task 7: `finish` 入队，永不因 Insights 失败而失败

**Files:**

- Modify: `apps/control-plane/api/src/yino_platform_api/services/call_lifecycle.py`
- Modify: `apps/control-plane/api/src/yino_platform_api/app.py`（注入 dispatch repo + customer_services.get 取 slug）
- Modify: `tests/test_call_session_api.py` 或新建 `tests/test_call_lifecycle_insights.py`

**Interfaces:**

- Consumes: Task 4 slug、Task 5 `enqueue`、Task 6 `build_ended_call_body`
- `CallLifecycleService.__init__` 增加可选 `insights_dispatch: InsightsDispatchRepository | None = None`

逻辑（在 `save` 成功且意向抽取之后）：

1. `insights_dispatch is None` → 什么都不做。
2. `customer_services.get(record.customer_service_id, tenant_id)`，`insights_profile is None` → 不入队。
3. `not record.messages` → 不入队。
4. 否则 `enqueue`；`enqueue` 抛错要 **吞掉并打日志不得让 finish 抛错**（测试可用假仓库 raise，断言 finish 仍返回 completed）。

- [ ] **Step 1: API/生命周期测试**

```python
def test_finish_without_binding_does_not_enqueue(ids) -> None:
    repo = InMemoryInsightsDispatchRepository()
    # demo 实例 insights_profile is None
    # start + message + finish
    assert repo.all() == []

def test_finish_with_binding_enqueues_and_survives_queue_error(ids) -> None:
    instance = demo.model_copy(update={"insights_profile": "demo-clinic"})
    # finish 201/200，jobs 一笔
    # 再测 RaisingRepo：finish 仍 200
```

- [ ] **Step 2: pytest 红**
- [ ] **Step 3: 实现并接到 `create_app`（内存与 postgres 模式都注入 repo）**
- [ ] **Step 4: `pytest tests/test_call_session_api.py tests/test_call_lifecycle_insights.py -q` 绿**

---

### Task 8: HTTP 投递工人（4xx 停、5xx 重试）

**Files:**

- Create: `apps/control-plane/api/src/yino_platform_api/services/insights_http.py`
- Modify: `apps/control-plane/api/src/yino_platform_api/config.py`、`.env.example`
- Modify: `app.py` lifespan：若 `insights_base_url` 与 `insights_ingest_token` 都有，则后台每 2 秒 `drain_once`；测试可注入 FakeTransport
- Test: `tests/test_insights_http.py`

**Interfaces:**

```python
async def post_ended_call(
    *,
    base_url: str,
    token: str,
    profile: str,
    body: dict[str, object],
    transport: httpx.AsyncClient | None = None,
) -> Literal["ok", "retry", "fail"]:
```

POST `{base_url.rstrip("/")}/v1/ingest/{profile}`  
Header `Authorization: Bearer {token}`  
`timeout=10.0`  
200/202 → `ok`；408/429/5xx/网络错 → `retry`；其它 4xx → `fail`

`drain_once(now)`：`claim_due` → post → mark_sent / mark_retry(指数退避 10s,40s,160s 封顶 15min) / mark_failed。

未配置 URL 或 token：不启动后台循环；已入队的行保持 pending（测试可手动 drain）。

- [ ] **Step 1: httpx mock 测试**（202→sent；500→仍 pending 且 attempts+1；404→failed）
- [ ] **Step 2: pytest 红**
- [ ] **Step 3: 实现**
- [ ] **Step 4: pytest 绿；`ruff check` 新文件**

---

### Task 9: 回归与文档指针

**Files:**

- Modify: `docs/platform/superpowers/specs/2026-08-25-call-insights-channel-contract-design.md` 状态改为「实施中」
- Insights：`npm test && npx tsc --noEmit`
- Yino API：`.\.venv\Scripts\python.exe -m pytest -q`（跳过需 DATABASE_URL 的照旧）

- [ ] **Step 1: 跑满 Insights 测试**
- [ ] **Step 2: 跑 Yino API pytest**
- [ ] **Step 3: 确认没有改 `POST /v1/vapi/:profile` 行为、没有改 lucaplus/inp-group 收件人文件**
- [ ] **Step 4: 不要 commit，除非用户要求**

---

## Spec coverage

| Spec | Task |
|------|------|
| 分仓、VAPI 路由不改 | 2、9 |
| `POST /v1/ingest/:profile`、独立口令 | 2 |
| 规范字段、去重 eventId | 1、6 |
| recordingUrl null、summary 空 | 1、6 |
| 默认不发 Yino 邮件，mailEnabled 才发 | 3 |
| 未绑定不投递 | 7 |
| 挂断成功不依赖 Insights | 7、8 |
| 未知 profile 4xx 永久失败 | 8 |
| 5xx 重试 | 8 |
| 不自动建客户 | 2 |
| 不做录音/并仓/改 VAPI URL | 全局 |

## 执行方式

计划写在 `docs/platform/superpowers/plans/2026-08-25-call-insights-channel-contract.md`。

**1. Subagent-Driven（推荐）** — 每个 Task 新开子代理，Task 之间你过目  
**2. Inline Execution** — 本会话按 executing-plans 逐项做  

你要哪一种？
