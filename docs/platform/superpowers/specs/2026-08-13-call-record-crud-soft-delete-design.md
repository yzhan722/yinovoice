# 通话记录 CRUD（软删除）设计

日期：2026-08-13  
状态：已在 Stage1 实施并冒烟通过（生产未部署）  
范围：Control Plane 通话记录；先 Stage1 验证，不上生产  
仓库：`E:\Repos\yinovoice`

## 目标

补齐通话记录的 **改、删**，与现有增、查一起形成租户内 CRUD；删除采用 **软删除**。

## 非目标

- 不做实例删除/停用（A3，另议）
- 不做跨租户运营审计后台、全文搜索（可后续接 TASKS B）
- 不把录音文件物理删除纳入本轮（软删记录后录音文件可保留；硬清文件另议）
- 不自动 commit / 不上生产

## 现状

| 能力 | 状态 |
|------|------|
| POST `/api/v1/call-records` | 已有 |
| GET 列表 / GET 详情 | 已有 |
| 录音上传/播放 | 已有 |
| PUT 更新 | 无 |
| DELETE | 无 |
| `deleted_at` | 无 |

## 数据模型

`call_records` 增加：

- `deleted_at TIMESTAMPTZ NULL`：`NULL` = 未删除；非空 = 软删除时间（UTC）

索引建议：

- 部分索引或普通索引支持列表过滤：`(tenant_id, deleted_at, created_at DESC)`（实现时按现有风格选一种）

`call_messages`：**不单独软删**；随所属通话记录一起对用户不可见。软删不级联物理删除 messages，便于恢复。

Alembic 新版本：`20260813_0002_call_records_soft_delete`（名称以落地为准）。

## API

租户头：`X-Tenant-ID`（与现网一致）。

### 查（调整）

- `GET /api/v1/call-records`  
  - 默认：`deleted_at IS NULL`  
  - 可选：`include_deleted=true`（仅 Demo/联调；运营端可先共用）  
- `GET /api/v1/call-records/{id}`  
  - 未删除：200  
  - 已软删或不存在：404（租户视角一致）

### 改

- `PUT /api/v1/call-records/{id}`  
- 请求体 `CallRecordUpdate`（建议字段）：  
  - `status`（completed / interrupted / failed）  
  - `messages`（可选；若提供则整单替换转写，校验 sequence 规则与现 Create 一致）  
  - 不改：`id` / `tenant_id` / `customer_service_id` / `created_at` / 录音元数据（录音仍走现有 upload 接口）  
- 已软删：404  
- 成功：200 + 完整 `CallRecord`（`deleted_at` 对未删为 null，可不暴露或暴露为 null）

### 删（软删除）

- `DELETE /api/v1/call-records/{id}`  
- 行为：设置 `deleted_at = now(UTC)`；幂等：已删再删仍 204/200（推荐 204）  
- 不存在：404  
- 不删除 `call_messages` 行、不删录音文件

### 恢复（本轮最小集）

- `POST /api/v1/call-records/{id}/restore`  
- 将 `deleted_at` 置回 `NULL`  
- 仅当记录存在且已软删：200；未删：200（幂等）或 409（二选一，推荐幂等 200）；不存在：404  

## 仓库层

- `InMemoryCallRecordRepository` 与 `PostgresCallRecordRepository` 同步支持：  
  `list` 过滤、`soft_delete`、`restore`、`update`  
- Postgres `save` 更新路径需支持 `deleted_at` 读写  

## 前端（Stage1 可操作）

通话记录列表 / 详情（用户端）：

- 列表：每行增加「删除」；确认后调 DELETE；成功刷新列表  
- 详情：展示转写；增加「删除」；可选「恢复」若从带 `include_deleted` 的入口进入（本轮可只做删除，恢复用 API/后续）  
- 详情：允许编辑 `status` + 转写文本并保存（PUT）；失败保留输入并提示  
- 默认列表不显示已删记录  

不改生产前端部署，直至用户授权 Stage1 部署本功能。

## 验证

本地：

- API 单测：软删后列表不可见、详情 404、restore 后可见、PUT 更新 messages/status  
- Web 单测：删除确认与刷新；保存更新  

Stage1（授权后）：

- 迁移应用到 `yino_platform_stage1`（**不对生产库跑**，除非另授）  
- 网页：删一条 → 列表消失 → restore（API 或后续 UI）→ 再现  
- 生产库 `call_records` 行数与 `deleted_at` 列状态不受影响（生产未部署则无该列）

## 风险

| 风险 | 缓解 |
|------|------|
| 误对生产跑迁移 | Stage1 脚本/手工只指向 `yino_platform_stage1` |
| 旧前端缓存 | Stage1 重新 build 部署 |
| 软删后录音仍占磁盘 | 本轮接受；清理策略另开任务 |

## 明确不做

- 硬删除 API  
- 搜索、分页以外的复杂筛选  
- 实例 A3  
