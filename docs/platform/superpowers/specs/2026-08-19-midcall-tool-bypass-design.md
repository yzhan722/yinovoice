# 通话中 Tool 旁路（Mid-call Tool Bypass）设计

日期：2026-08-19  
状态：待审阅  
范围：Control Plane API + voice-agent；先 Stage1；不上生产  
仓库：`E:\Repos\yinovoice`  
前置：`2026-08-18-appointments-callbacks-phase2-extract-design.md`  
约束：Qwen Realtime **无原生 Function Tool** → 用命名 Tool HTTP API + agent 侧解析旁路，对齐 Vapi「通话中可写业务」

## 目标

通话进行中即可结构化写入：

- `create_appointment` → `appointments`（`source=voice_tool`）
- `create_callback` → `callback_tasks`（`source=voice_tool`）

并留下可审计的 `tool_invocations` 记录；通话抽屉可展示调用结果。  
挂断后的 Phase2 `extract-intents` **保留为兜底**（已有成功写入则跳过）。

## 非目标

- Qwen / LiveKit 原生 Function Tool  
- `transfer_human` / 挂机 Tool（后置）  
- Google Calendar、医生档期冲突引擎  
- 外呼 Campaign、生产部署  
- 完整 Logs / Cost Tab（本期仅抽屉内简短 Tool 条）

## 方案选择

| 方案 | 结论 |
|------|------|
| A：命名 Tool API + 标记优先/规则兜底 | **采用**（最接近 Vapi 且可测） |
| B：仅强化挂断抽取 | 不做为本期主路径 |
| C：硬开 Qwen Realtime tools | 能力门拒绝，不可行 |

## 架构

```
用户说话 → Qwen 转写 / 回复
         → voice-agent：
              1) 从 assistant final 剥标记 [[tool:...]]
              2) 若无标记，规则兜底（转写命中预约/回拨且字段够）
         → POST /api/v1/tool-invocations
         → 落 tool_invocations + 写 appointment / callback
         → 返回 result；agent 可向会话注入简短确认（不朗读标记）
挂断 → POST/PUT call-records → extract-intents
         → 若同 call/session 已有成功 tool 写入则跳过
```

会话关联键：`session_id` = LiveKit `room_name`（通话记录已有该字段）。

## 数据模型

### `tool_invocations`（新表）

| 字段 | 说明 |
|------|------|
| `id` | UUID PK |
| `tenant_id` | 租户 |
| `session_id` | = `room_name`，通话中必填 |
| `call_record_id` | 可空；结束落库后回填或创建时带上 |
| `voice_agent_instance_id` | 可空 |
| `tool_name` | `create_appointment` \| `create_callback` |
| `arguments_json` | 调用参数 |
| `status` | `ok` \| `error` \| `skipped` |
| `result_json` | 含 message、appointment_id / callback_task_id 等 |
| `idempotency_key` | 应用层去重键（见下） |
| `created_at` | 时间 |

索引：`(tenant_id, session_id)`；`(tenant_id, call_record_id)`；唯一建议 `(tenant_id, idempotency_key)`（若 DB 支持；否则应用层查重）。

### 预约 / 回拨

- 继续写现有表；`source=voice_tool`  
- 可选：`notes` 或 result 中带 `tool_invocation_id`（若加列成本高，可只放在 `tool_invocations.result_json` 与 notes 文本）

### 幂等

同租户下，下列任一命中则不再新建业务行，返回已有 id：

1. 已有 `idempotency_key` 相同的成功 invocation  
2. 同 `session_id`（或已绑 `call_record_id`）已成功执行过**同名** tool（首批：每会话每 tool 成功至多一次；冷却防连打）

`idempotency_key` 建议：`{session_id}:{tool_name}:{fingerprint}`，fingerprint 为规范化后的 phone+service 或 phone+reason 哈希。

## API

### `POST /api/v1/tool-invocations`

请求：

```json
{
  "session_id": "room-xxx",
  "call_record_id": null,
  "voice_agent_instance_id": "uuid-or-null",
  "tool_name": "create_appointment",
  "arguments": {
    "patient_name": "王女士",
    "phone": "13800000000",
    "service": "洁牙",
    "slot_start": null,
    "slot_end": null,
    "reason": null,
    "summary": null
  },
  "idempotency_key": "可选；服务端也可自算"
}
```

`create_appointment` 缺电话/时段：沿用 Phase2 方案 A（占位电话/下一工作日上午 + notes 待确认）。  
`create_callback`：至少需要电话或「待确认电话」+ reason/summary。

响应 `200`：

```json
{
  "invocation_id": "...",
  "status": "ok",
  "tool_name": "create_appointment",
  "result": {
    "message": "已登记预约意向…",
    "appointment_id": "...",
    "callback_task_id": null
  }
}
```

错误：`400` 参数非法；`404` 若强绑了不存在的 call_record；业务写失败 → **HTTP 200 + `status=error`**（避免打断语音环）。

鉴权：现有 `X-Tenant-ID`；Stage1 voice-agent 经内网 `PLATFORM_API_URL` 调用，租户 id 从 dispatch metadata / runtime config 注入（与现有实例配置拉取一致）。

### `GET /api/v1/tool-invocations?session_id=` 或 `?call_record_id=`

供抽屉展示；租户隔离；按 `created_at` 升序。

### 与 Phase2 抽取的衔接

- `persist_extracted_intents`：若同 `call_record_id` **或** 该记录 `room_name` 对应 session 已有成功的 `create_appointment` / `create_callback`，则 `skipped_reason=tool_already_wrote`  
- 通话 `POST` 创建时若带 `room_name`，尝试把未绑定的 `tool_invocations` 按 `session_id=room_name` 回填 `call_record_id`

## Agent 侧

### 标记协议（优先）

Prompt（平台/演示）要求：在用户已确认意向且关键字段已齐（或明确「先登记待确认」）后，在回复**末尾**追加一行（不对用户朗读）：

```text
[[tool:create_appointment|patient_name=王女士|phone=13800000000|service=洁牙]]
```

或：

```text
[[tool:create_callback|phone=13800000000|reason=要求回电确认预约]]
```

- TTS / 用户可见字幕：**剥掉** `[[tool:...]]` 整段  
- 仅处理 assistant **final** 文本，避免 partial 连触发  

### 规则兜底

无标记时：对近期 user(+assistant) 文本跑与 `intent_extract` **同源或共享** 的启发式；字段达到「可写」阈值才调用 API。  
同会话成功一次后进入冷却（例如该 tool 不再自动触发，除非新标记）。

### HTTP 客户端

复用 `PLATFORM_API_URL` + `httpx`（`server.py` / runtime config 已有模式）。失败只打日志，不中断通话。

## 前端

- `CallRecordDetailDrawer`（及详情页可选）：增加「Tool 调用」区块，拉 `GET tool-invocations?call_record_id=`  
- 展示：tool 名、时间、结果摘要（成功/失败）  
- 预约列表「语音自动」逻辑不变  

## 复用

- 写库逻辑：抽共享 service（从 `intent_extract.persist_*` 拆出 `apply_appointment_intent` / `apply_callback_intent`），供 Tool API 与挂断抽取共用  
- `platform-core` booking/handoff：**本期不接线**；仅对齐命名与「需确认」语义；真编排后置  

## 验证

- API 单测：create_appointment / create_callback / 幂等 / 非法 tool_name  
- Agent 单测：标记解析、剥 TTS、规则兜底冷却  
- 抽取衔接：已有 tool 成功 → extract skip  
- Stage1（另授）：通话中说清意向+电话 → 未挂断前预约列表可见；抽屉有 invocation；挂断不重复  

## 明确不做

- 原生 Realtime tools  
- 转人工 / 挂机 Tool  
- 生产部署（另授）  
