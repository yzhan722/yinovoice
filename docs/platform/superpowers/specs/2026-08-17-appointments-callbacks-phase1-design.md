# C：预约结果 + 回拨任务（真实化）设计

日期：2026-08-17  
状态：实施中（Phase 1）  
范围：Control Plane；先 Stage1；不上生产  
仓库：`E:\Repos\yinovoice`  
对齐：`TASKS.md` C；对比基准 Vapi Calendar / Callback 闭环

## 目标

把租户端「预约结果」「回拨任务」从 **演示/mock** 升级为 **租户隔离的真实 CRUD**，数据落 Postgres，网页可操作。

## 分期

| 期 | 内容 | 本期 |
|----|------|------|
| **Phase 1** | 表结构 + API + 网页列表/新建/状态变更 | **现在做** |
| **Phase 2** | 语音 Tool：`create_appointment` / `create_callback`；调整 Prompt 允许登记意向 | 设计预留，另开实现 |
| **Phase 3** | 真外呼（Twilio/SIP）、拨打中状态 | 不做 |

## 非目标（Phase 1）

- 真实拨出电话 / 号码绑定  
- Google Calendar 同步  
- 完整排班冲突引擎、医生资源日历  
- 级联删除通话记录  
- 自动 commit / 部署生产  

## 现状

| 项 | 状态 |
|----|------|
| 页面 `/user/appointments` | UI 有；`TenantAppointmentService` → mock |
| 页面 `/user/callback-tasks` | 明确「电话未接通」占位 |
| API / DB | 无对应表 |
| 口腔 Demo Prompt | 禁止代登记预约（Phase 2 再改） |

## 数据模型

### `appointments`

| 列 | 类型 | 说明 |
|----|------|------|
| id | UUID PK | |
| tenant_id | UUID | 租户 |
| voice_agent_instance_id | UUID NULL | 可选关联实例；FK → `voice_agent_instances (tenant_id, id)` |
| call_record_id | UUID NULL | 可选关联通话；无强 FK（通话可软删） |
| patient_name | VARCHAR(80) | |
| phone | VARCHAR(32) | 联系电话（可存完整号；列表可前端脱敏） |
| service | VARCHAR(120) | 项目/事由 |
| slot_start | TIMESTAMPTZ | |
| slot_end | TIMESTAMPTZ | 须 ≥ slot_start |
| status | TEXT | `pending` / `confirmed` / `cancelled` |
| source | TEXT | `manual` / `voice_tool` / `import`（Phase1 默认 `manual`） |
| notes | TEXT | 可选备注，默认 `''` |
| created_at / updated_at | TIMESTAMPTZ | |

索引：`(tenant_id, slot_start)`；`(tenant_id, status)`。

### `callback_tasks`

| 列 | 类型 | 说明 |
|----|------|------|
| id | UUID PK | |
| tenant_id | UUID | |
| voice_agent_instance_id | UUID NULL | 可选 |
| call_record_id | UUID NULL | 可选 |
| caller_phone | VARCHAR(32) | |
| reason | VARCHAR(200) | |
| summary | TEXT | 默认 `''` |
| status | TEXT | `open` / `done` / `cancelled` |
| source | TEXT | `manual` / `voice_tool` / `from_call` |
| created_at / updated_at | TIMESTAMPTZ | |

索引：`(tenant_id, status, created_at DESC)`。

Alembic：`20260817_0004_appointments_callbacks`（revises `20260817_0003`）。

## API

前缀：

- `/api/v1/appointments`
- `/api/v1/callback-tasks`

租户头：`X-Tenant-ID`。

### 预约

| 方法 | 路径 | 行为 |
|------|------|------|
| GET | `` | 列表；`status` 可选；`limit`/`offset`；默认不含 `cancelled` 除非 `include_cancelled=true` |
| POST | `` | 创建；`status` 默认 `pending`；`source=manual` |
| GET | `/{id}` | 详情；跨租户/不存在 → 404 |
| PATCH | `/{id}` | 更新 `status` 及可选字段（姓名/电话/服务/时段/notes） |
| DELETE | `/{id}` | **软语义**：`status=cancelled`（204）；已取消再删幂等 |

请求体（Create）关键字段：`patient_name`, `phone`, `service`, `slot_start`, `slot_end`；可选 `voice_agent_instance_id`, `notes`。  
若提供实例 id：须存在且未软删，否则 404。

### 回拨

| 方法 | 路径 | 行为 |
|------|------|------|
| GET | `` | 列表；`status` 可选；默认返回非 `cancelled` |
| POST | `` | 创建；`status=open`；`source=manual` |
| GET | `/{id}` | 详情 |
| PATCH | `/{id}` | 更新 status / reason / summary / phone |
| POST | `/{id}/complete` | 置 `done`（幂等 200） |
| POST | `/{id}/reopen` | 置 `open`（幂等 200） |

## 仓库层

InMemory + Postgres 双实现；`app.py` 接线与通话记录相同模式。

## 前端（Phase 1）

### 预约页

- 去掉「规划中 · 演示框架」主文案  
- `TenantAppointmentService` 改打真 API；字段映射 snake ↔ 现有 camel  
- 增加「新建预约」简单表单  
- 列表/日历读真数据；支持 confirmed / cancelled  

### 回拨页

- 替换整页占位为任务列表  
- 新建回拨意向；完成 / 重开  
- 页头注明：**本阶段不发起真实外呼**，仅任务队列  

### 测试

- 更新 `planned-modules.test.ts`：不再断言「规划中」占位  
- API pytest：创建/列表租户隔离/完成回拨/取消预约  

## Phase 2 预留（不实现）

- 语音 Tool：`create_appointment` / `create_callback`  
- 调整平台 Prompt：允许登记**意向**，禁止宣称「已挂号成功」  
- `source=voice_tool`，可选 `call_record_id`  

## 验证

本地：pytest + vitest。  
Stage1（另授）：迁移 `yino_platform_stage1` → 网页建预约/回拨 → 刷新仍在；生产库无新表写操作。

## 风险

| 风险 | 缓解 |
|------|------|
| 误对生产跑迁移 | 仅 Stage1 |
| 电话号码隐私 | Phase1 存库；不下生产 |
| Prompt 仍禁止预约 | Phase1 仅人工录入，不冲突 |

## 明确不做（本期）

- 真拨号  
- Google Calendar  
- Phase 2 Tool（仅文档预留）  
