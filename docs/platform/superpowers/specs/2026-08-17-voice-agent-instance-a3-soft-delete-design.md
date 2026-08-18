# Voice Agent Instance A3（软删除 + 条件硬删）设计

日期：2026-08-17  
状态：本地已实现；待 Stage1 部署验收（生产未部署）  
范围：Control Plane 语音实例（customer-services）；先 Stage1 验证，不上生产  
仓库：`E:\Repos\yinovoice`  
对齐：`2026-08-13-call-record-crud-soft-delete-design.md`

## 目标

为租户语音实例补齐：

1. **软删除 / 恢复**（与通话记录同一套 `deleted_at` 语义）
2. **完全删除（硬删）**：仅出现在「已软删」视图；若仍有关联通话记录则 **禁止**（409）

默认列表不可见已软删；可勾选「显示已删除」后恢复或（在无通话时）完全删除。

## 非目标

- 级联硬删 / 软删关联 `call_records`、`call_messages` 或录音文件（有通话时不允许硬删实例）
- 单独的 `status=disabled` 停用态（与软删除并存本期不做）
- 未软删直接硬删（UI/API 均要求先软删）
- 跨租户运营审计、全文搜索
- 自动 commit / push / 部署生产

## 现状

| 能力 | 状态 |
|------|------|
| GET 列表 / GET 详情 | 已有 |
| POST 创建（A2） | 已有 |
| PUT 更新 | 已有 |
| LiveKit token | 已有 |
| DELETE / restore / purge | 无 |
| `voice_agent_instances.deleted_at` | 无 |

## 数据模型

`voice_agent_instances` 增加：

- `deleted_at TIMESTAMPTZ NULL`：`NULL` = 有效；非空 = 软删除时间（UTC）

索引建议（实现时按现有风格择一）：

- `(tenant_id, deleted_at)` 或等价，便于默认列表过滤

Alembic 新版本：`20260817_0003_voice_agent_instances_soft_delete`（名称以落地为准）。

### 关联数据保留策略

- **通话记录**：软删实例时 **始终保留**；继续用原 `voice_agent_instance_id` 可读可查。
- **硬删实例**：仅当该实例下 **不存在任何** `call_records` 行（含已软删通话）时允许；存在则 409，不改通话数据。
- **实例配置行**：软删后行仍在，便于 restore；硬删后行物理删除。
- **前端选择器**（助手 / 实时通话 / 知识库）：默认列表不含已软删；本地若仍缓存已删 id，GET/更新/发 token 走 404。

> 说明：统计「是否有通话」时包含 `call_records.deleted_at IS NOT NULL` 的行，避免硬删实例后留下无法挂靠的通话外键孤儿（FK 仍指向实例）。

## API

租户头：`X-Tenant-ID`（与现网一致）。

领域模型 `CustomerServiceInstance` 增加可选字段：

- `deleted_at: datetime | None = None`（未删为 `null`）

### 查（调整）

- `GET /api/v1/customer-services`  
  - 默认：`deleted_at IS NULL`  
  - 可选：`include_deleted=true`  
- `GET /api/v1/customer-services/{id}`  
  - 未软删：200  
  - 已软删或不存在：404

### 改 / 发 token（收紧）

- `PUT /api/v1/customer-services/{id}`：已软删 → 404  
- `POST /api/v1/customer-services/{id}/livekit-token`：已软删 → 404  

（`get` 统一过滤已软删即可覆盖上述路径。）

### 软删除

- `DELETE /api/v1/customer-services/{id}`  
- 行为：`deleted_at = now(UTC)`；幂等：已软删再删仍 **204**  
- 不存在：404  
- 不删关联通话与录音

### 恢复

- `POST /api/v1/customer-services/{id}/restore`  
- 将 `deleted_at` 置回 `NULL`  
- 存在且已删或未删：均 **200**（幂等）+ 完整实例；不存在：404  

### 完全删除（硬删）

- `POST /api/v1/customer-services/{id}/purge`  
  （选用 POST 路径，避免与软删 `DELETE` 语义冲突；不使用 query 开关。）

前置与结果：

| 条件 | 响应 |
|------|------|
| 实例不存在 | 404 |
| 实例未软删（`deleted_at IS NULL`） | 409，detail 说明须先软删除 |
| 存在任意关联 `call_records`（含已软删通话） | 409，detail 说明须先处理通话记录 |
| 已软删且无关联通话 | **204**，物理删除实例行 |

不级联删模板版本；不删录音文件（本就无通话时通常也无关联录音）。

## 仓库层

`CustomerServiceRepository`（InMemory + Postgres）同步支持：

- `list_for_tenant(..., include_deleted: bool = False)`
- `get`：已软删视为不存在（返回 `None`），供详情 / PUT / token  
- 内部 `get_including_deleted`（或等价）供 soft_delete / restore / purge  
- `soft_delete(instance_id, tenant_id)`  
- `restore(instance_id, tenant_id) -> CustomerServiceInstance | None`  
- `purge(instance_id, tenant_id)`：返回区分结果（ok / not_found / not_soft_deleted / has_call_records），由路由映射 204/404/409  

Postgres 硬删前先 `EXISTS` 查询 `call_records`（同 `tenant_id` + `voice_agent_instance_id`）。  
ORM `VoiceAgentInstance` 与 `_to_domain` / `save` / `create` 读写 `deleted_at`。

## 前端（Stage1 可操作）

主要入口：**助手设置 → 我的实例**（`assistant-settings/index.vue`）：

- 列表默认不拉已软删；增加「显示已删除」勾选（`include_deleted=true`）
- **未删行**：确认后「软删除」→ `DELETE` → 刷新  
- **已软删行**：  
  - 「恢复」→ `POST .../restore`  
  - 「完全删除」→ 二次确认（文案强调不可恢复、有通话将失败）→ `POST .../purge`  
  - purge 409：页面提示「该实例下仍有通话记录，无法完全删除」  
- `RealtimeVoiceService`：补 `deleted_at`、`deleteCustomerService`、`restoreCustomerService`、`purgeCustomerService`、列表 `include_deleted`

实时通话 / 知识库：继续默认列表（不含已软删）；本轮不加删除 UI。

样式与交互对齐通话记录列表（确认文案、已删行样式）；「完全删除」用更醒目的危险操作样式。

## 验证

本地：

- API：软删后默认列表不可见、详情/PUT/token 404、`include_deleted` 可见、restore 可用  
- API：未软删 purge → 409；有通话 purge → 409；无通话已软删 purge → 204 且列表/含删列表均不可见  
- Web：软删 / 显示已删除 / 恢复；完全删除成功与 409 提示

Stage1（授权后）：

- 迁移只应用到 `yino_platform_stage1`  
- 网页走通软删 → 恢复；再建无通话实例走软删 → 完全删除  
- 对有通话的已软删实例点完全删除，应看到失败提示且实例仍在  
- **不对生产库跑迁移**，除非另授

## 风险

| 风险 | 缓解 |
|------|------|
| 误对生产跑迁移 | Stage1 只指向 `yino_platform_stage1` |
| 误点完全删除 | 仅已软删可见 + 二次确认；有通话则 409 |
| 软删通话仍挡硬删 | 按设计有意为之，避免 FK 孤儿；文档写明 |
| 本地仍选中已软删实例 | GET/token 404 |

## 明确不做

- 有通话时仍硬删实例或级联清通话  
- 未软删直接 purge  
- `status` 停用与软删除双轨  
- 生产部署（需另一次明确授权）
