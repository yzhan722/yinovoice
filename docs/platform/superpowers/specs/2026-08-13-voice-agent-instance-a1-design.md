# Voice Agent Instance A1 真实数据闭环设计

## 目标

在不新增数据库表、不实现创建或删除的前提下，让当前租户能够从 PostgreSQL 读取 Voice Agent Instance 列表、选择实例、查看和编辑配置，并让知识库与实时通话入口使用选中的 UUID，而不是固定 Demo ID。

## 领域语言

- 对外统一使用 **Voice Agent Instance（语音 Agent 实例）**。
- 后端现有 `/customer-services` 路径本轮保持兼容，不借本功能重命名公共路径。
- UUID `id` 是实例唯一标识；旧前端数字 `attId` 只保留在未迁移的旧页面兼容层中。
- 当前租户由 Demo 阶段的 `X-Tenant-ID` 提供；所有列表、详情和修改都必须按租户隔离。

## 后端接口

新增：

```http
GET /api/v1/customer-services?limit=20&offset=0
X-Tenant-ID: <tenant UUID>
```

响应：

```json
{
  "items": [],
  "total": 0
}
```

要求：

- `limit` 范围 1–100，默认 20；`offset` 大于等于 0。
- 只返回 `X-Tenant-ID` 对应租户的数据。
- 按 `updated_at DESC, id DESC` 稳定排序。
- In-memory 与 PostgreSQL adapter 提供相同接口。
- 现有详情、修改和乐观版本冲突行为保持不变。

## 前端模块

在 `RealtimeVoiceService` 中增加实例分页读取，并作为当前 Platform API 的统一接口。新增轻量的实例选择状态模块：

- 从路由查询参数 `instanceId` 读取当前选择；
- 无查询参数时使用 sessionStorage 中最近一次有效选择；
- 两者都没有时选择列表第一项；
- 列表为空时显示空状态，不回退到不存在的固定实例；
- 旧 Demo ID 只保留为开发配置兼容，不再作为真实列表页的隐式选择。

“我的实例”页面改为读取真实列表，使用 UUID 跳转。实例详情页本轮不重写大型旧表单；新增/复用一条 Platform 配置编辑入口，确保读取和保存走 `GET/PUT /customer-services/{uuid}`。知识库和实时通话页面读取当前实例选择。

## 错误处理

- 401/403/404/409/422/5xx 不向用户暴露服务端敏感正文。
- 版本冲突继续显示“配置已被更新，请刷新后重试”。
- 列表失败显示可重试错误，不伪装为空列表。
- 当前选择不在最新列表时清除旧选择并回退到第一项。

## 非目标

- 不实现创建、物理删除、停用或归档。
- 不新增 Template Version API。
- 不修改 Tenant/RBAC、SIP、录音保留或通话删除。
- 不删除旧 WRequest 页面、mock、部署快照或旧兼容字段。

## 验收

1. API 的列表分页、租户隔离、稳定排序通过内存与 PostgreSQL 测试。
2. 前端列表显示真实 UUID 实例并可选择。
3. 详情和修改使用选中 UUID，修改后刷新仍返回新值。
4. 实时通话签发 token 和写入 Call Record 使用选中 UUID。
5. 知识库配置页使用选中 UUID。
6. 现有 API、Runtime 和前端测试不回归。
