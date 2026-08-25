# 商业 MVP 入站电话闭环设计

日期：2026-08-24  
状态：已对照当前仓库落地  
仓库：`C:\Users\yino\Projects\yinovoice`（`yzhan722/yinovoice` @ `79d531d`）  
任务来源：

- `YinoVoice 下一阶段商业 MVP 任务清单.md`（产品范围）
- `yinovoice_cursor_grok46_commercial_mvp_task.md`（实施合同）

以当前代码为事实来源。不引入第二套同义模块。本阶段不提交、不推送、不部署。

## 1. 仓库对照（相对任务书路径）

| 任务书 | 本仓库 |
|---|---|
| `apps/control-plane/api` + `yino_platform_api` | `apps/control-plane/api` + `yino_platform_api` |
| `apps/control-plane/web` Vue 3 TDesign | 实际为 **Vue 3 + TDesign**（`tdesign-vue-next`） |
| `apps/runtime/voice-agent` + `yino_voice_agent` | `apps/runtime/voice-agent` + `yino_voice_agent` |
| `X-Tenant-ID` | `X-Tenant-ID` |
| Dispatch 三字段 | `customer_service_id` / `tenant_id` / `config_version` |
| Alembic head | `20260817_0004`（appointments / callback_tasks） |
| 通话中 Tool 设计 | `docs/platform/superpowers/specs/2026-08-19-midcall-tool-bypass-design.md`（尚未写入运行代码） |
| `deploy/src` | 历史快照；本阶段只改 `apps/` |

实例在 API/领域层叫 `CustomerServiceInstance`，表名为 `voice_agent_instances`。电话绑定字段使用 `voice_agent_instance_id`，与预约表一致；Dispatch metadata 继续用 `customer_service_id`（同一 UUID）。

## 2. 产品决定（不再提问）

采用 grok 任务书中已固定的决定：

1. 通道：LiveKit SIP 入站 + 现有 LiveKit Agents / Qwen Realtime。只做入站，不做批量外呼。
2. 预约权威：Yino 内建单资源排期。不接 Google Calendar / HIS。
3. 人工：不建真实转接；`create_callback` 承接人工请求。
4. 通话中 Tool：隐藏标记旁路。MVP 三个工具：`check_availability`、`create_appointment`、`create_callback`。
5. 录音：Web 维持现有本机上传；SIP 用 LiveKit Egress → S3 兼容存储。
6. 通知：SMTP。失败不回滚预约/回拨。
7. 认证：继续 Demo `X-Tenant-ID`。本阶段不做登录/RBAC/计费。
8. 缺 SIP/S3/SMTP 真凭据时：代码 + Fake + 测试 + 配置模板 + 手工清单照常交付。

与中文清单的收敛：清单中的“转人工或回拨”按 grok 落实为只建回拨；“Google Calendar 或自有排期”按 grok 落实为自有排期。

## 3. 与现有模型的兼容映射

### 3.1 通话方向

- 领域层 `CallRecord.direction` 目前仅 `web`。
- 表 `call_records` 的 check 已允许 `web | inbound | outbound`。
- SIP 入站写入 **`inbound`**，不新增 `sip_inbound` 枚举，避免第三套同义词。
- Runtime metadata 使用 `channel: "web" | "sip"`。`sip` 对应落库 `direction=inbound`。

### 3.2 通话生命周期

当前 `CallRecord` 要求 `started_at`、`ended_at`、`duration_sec` 均必填，只适合挂断后一次性保存。Milestone 2 将：

- `status` 增加 `in_progress`（并放宽“进行中记录可空 ended_at/duration”）。
- 新增 Runtime 生命周期 API，不破坏现有 `POST /api/v1/call-records`。

### 3.3 挂断抽取

`services/intent_extract.py` 在缺时间时会填下一工作日上午。Milestone 3 删除该商业路径：缺有效 slot 只能建回拨或跳过，不得造预约。

### 3.4 Tool 协议

沿用 2026-08-19 设计的单行标记，并扩展 `check_availability`。标记不得进入 TTS、字幕或 `call_messages`。

## 4. 目标链路

```text
PSTN
  → LiveKit SIP Inbound Trunk + Dispatch Rule
  → Room（metadata 含 tenant / customer_service_id / config_version / channel=sip / 号码）
  → apps/runtime/voice-agent（Qwen Realtime）
       → POST /api/v1/call-sessions/start|messages|finish
       → POST /api/v1/tool-invocations
  → apps/control-plane/api
       → PostgreSQL（号码、通话、排期、预约、回拨、Tool 审计、通知事件）
  → LiveKit Egress → S3
  → SMTP
  → apps/control-plane/web（TDesign）
```

Yino 仍是业务与配置唯一事实来源。n8n / Vapi 不进入实时通话。

## 5. Milestone 1 数据与 API

### 5.1 表 `phone_numbers`

| 列 | 约束 |
|---|---|
| `id` UUID PK | |
| `tenant_id` UUID | NOT NULL |
| `voice_agent_instance_id` UUID | NOT NULL |
| `e164_number` TEXT | 规范化后 **全局唯一** |
| `provider` TEXT | 仅 `livekit_sip` |
| `inbound_trunk_id` TEXT | 可空 |
| `dispatch_rule_id` TEXT | 可空 |
| `enabled` BOOLEAN | 默认 true |
| `created_at` / `updated_at` | timestamptz |

外键：`(tenant_id, voice_agent_instance_id)` → `voice_agent_instances (tenant_id, id)`。  
号码只能绑定当前租户、`deleted_at IS NULL` 的实例。一个实例可有多个号码。

E.164：去掉空格/括号/连字符后必须匹配 `^\+[1-9]\d{7,14}$`。非法输入 422。

### 5.2 HTTP

前缀 `/api/v1/phone-numbers`，CRUD 需要 `X-Tenant-ID`。

- `GET /api/v1/phone-numbers`
- `POST /api/v1/phone-numbers`
- `PUT /api/v1/phone-numbers/{id}`
- `DELETE /api/v1/phone-numbers/{id}`
- `GET /api/v1/phone-numbers/lookup?number=`

`lookup` 按全局唯一 E.164 解析，不依赖租户头（SIP 入站时尚未知道租户）。禁用或不存在返回 404。成功体：

```json
{
  "id": "...",
  "tenant_id": "...",
  "voice_agent_instance_id": "...",
  "config_version": 1,
  "e164_number": "+61400000001",
  "provider": "livekit_sip",
  "inbound_trunk_id": null,
  "dispatch_rule_id": null,
  "enabled": true
}
```

`config_version` 来自绑定实例的 `version`。重复号码 409。跨租户绑定实例 404（不泄露他租户实例）。

### 5.3 Dispatch metadata

必填三字段保持不变，继续拒绝未知键和重复 JSON key。新增可选字段：

- `channel`: `"web"`（默认）或 `"sip"`
- `caller_number`, `callee_number`: 缺省或 JSON null；若出现则须为 E.164
- `provider_call_id`, `sip_trunk_id`: 缺省或 JSON null；若出现则非空字符串

现有网页 dispatch JSON 不加这些字段，必须继续通过。

### 5.4 LiveKit SIP 配置生成

纯函数生成 dry-run 计划，不调用 LiveKit、不读真实密钥：

- inbound trunk：`name=yino-inbound-{e164}`，`numbers=[e164]`
- dispatch rule：`roomPrefix=sip-`，`metadata` 为上述 JSON 字符串
- `trunk_ids` 在尚未创建时为 `["<replace-after-create>"]`

CLI：`scripts/provision_livekit_sip.py --dry-run ...`

## 6. 后续里程碑契约（本仓路径）

### M2 通话生命周期

新路由 `apps/control-plane/api/src/yino_platform_api/routes/call_sessions.py`：

- `POST /api/v1/call-sessions/start`
- `POST /api/v1/call-sessions/{id}/messages`（只收 final，sequence 严格递增，同 sequence 幂等）
- `POST /api/v1/call-sessions/{id}/finish`

Runtime 新增 `call_lifecycle.py`，由 `server.py` 编排。API 暂不可用不中断语音。

### M3 排期

新表：`service_offerings`、`business_hours`、`scheduling_profiles`、`schedule_exceptions`。  
`appointments.service_offering_id` 可空以兼容旧行。Availability 以实例本地时区生成 slot，UTC 查冲突；`pending`/`confirmed` 占用；创建时二次检查。

### M4–M5 Tool

表 `tool_invocations`；`POST /api/v1/tool-invocations` 业务错误 HTTP 200 + `status=error`。  
Runtime：`tool_protocol.py` / `tool_client.py` / `tool_orchestrator.py`。成功写入后挂断抽取 `skipped_reason=tool_already_wrote`。

### M6 录音

SIP：Egress 对象键 `recordings/{tenant_id}/{yyyy}/{mm}/{call_record_id}.ogg`。  
API 只存 egress id、object key、状态。Web 录音保持现有 blob。无配置则关闭且不影响通话。

### M7 通知

实例或租户级 `notification_email` + `notifications_enabled`。表 `notification_events`。`NotificationSink` + Fake / SMTP。

### M8 Web（TDesign）

新页：`pages/user/telephony/`、`pages/user/scheduling/`。增强通话抽屉、预约/回拨、Dashboard 真实 KPI。菜单仍由 `src/api/permission.ts` 驱动。

### M9

`.env.example`、合成冒烟脚本、手工 A–E 剧本。不部署生产。

## 7. 错误与测试

- Tool / 通知 / 录音失败不得终止实时对话。
- 可重试写必须有幂等键。
- 结构化日志含 `tenant_id`、`room_name`、`call_record_id`、`provider_call_id`，禁止密钥。
- 每个里程碑：领域测试、内存仓库、路由测试；Postgres 测试在 `DATABASE_URL` 存在时执行 alembic upgrade。
- 预存基线失败不计入本阶段回归（见实施计划）。

## 8. 基线测试（2026-08-24，本机）

| 模块 | 结果 | 说明 |
|---|---|---|
| API pytest | 84 passed, 5 failed, 12 skipped | 失败全部来自本机 `DATABASE_URL` 指向**未迁到 head** 的 Postgres（缺 `appointments` / `callback_tasks` / `deleted_at`）。`create_app()` 因此走 postgres 而不是 memory。 |
| API ruff | 68 issues | 既有迁移脚本与中文全角标点；本阶段不借机全仓清理。 |
| voice-agent pytest | 111 passed, 6 failed | 失败均在既有 `qwen_realtime*` / `test_providers`，与电话映射无关。 |
| voice-agent ruff | 6 issues | 均在既有 `qwen_realtime.py` 与测试。 |
| web | 未跑 | 当前 PowerShell 找不到 `pnpm`。Milestone 8 前用项目既有方式补跑。 |

这 5+6 个失败记为**原本失败**。本阶段引入的失败必须另计。
