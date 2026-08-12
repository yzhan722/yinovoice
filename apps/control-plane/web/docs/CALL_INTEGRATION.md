# 通话系统接入指南（路径 A）

第一阶段 Demo **不实现** SIP / 实时通话。本页说明收到通话项目 share 后如何 **立刻接入** Admin。

## 一键开关

`.env.development` / `.env.production`：

```env
VITE_CALL_SYSTEM_READY=false
# 设为 true 后，通话列表/详情走真实接口

# 可选：通话服务独立 Base（推荐）。为空则回退旧 UserEnum 路径
VITE_CALL_API_BASE=http://127.0.0.1:9xxx/
```

辅助：`src/mocks/shell.js` → `callSystemReady()`  
契约与归一化：`src/api/platform/callContract.js`  
唯一门面：`src/api/platform/TenantCallRecordService.js`

## 预留接口（当设置了 VITE_CALL_API_BASE）

| 用途 | Method | Path | Body（建议） |
|------|--------|------|----------------|
| 列表 | POST | `{BASE}api/tenant/calls/list` | `{ current, size, attId?, startedAtFrom?, startedAtTo? }` |
| 详情 | POST | `{BASE}api/tenant/calls/detail` | `{ aacId }` 或 `{ id }` |
| 统计（可选） | POST | `{BASE}api/tenant/calls/stats` | `{ range? }` → 工作台可替换演示曲线 |
| 实例选项 | POST | `{BASE}api/tenant/instances/options` | `{}` |

未设置 `VITE_CALL_API_BASE` 且 `READY=true` 时，回退：

- `UserEnum.CALL_HISTORY_LIST` / `CALL_HISTORY_DETAIL` / `ASSISTANT_OPTIONS`

## 列表项字段（归一化后）

门面会把多种命名映射为：

`aacId`, `callId`, `assistantName`, `attId`, `direction`, `status`, `startedAt`, `durationSec`, `customerPhone`, `success`

详情额外：`aacRecordingUrl`, `aacSummary`, `messages[]`（或 `transcript`）。

## 接入步骤（拿到 share 后）

1. 确认对方提供的 base URL、鉴权（若需改 `WRequest` 头，在门面内集中加，勿散落页面）。  
2. 对照上表改 `callContract.js` 的 `CALL_API_PATHS`（若路径不同）。  
3. `.env` 设置 `VITE_CALL_SYSTEM_READY=true` 与 `VITE_CALL_API_BASE=...`。  
4. 刷新 `#/user/call-history`，应出现表格；点行进详情。  
5. （可选）实现 `stats` 后，在工作台用 `getStats()` 替换演示曲线。  
6. **禁止** UI 暴露厂商 `syncCalls` / `syncAssistants`。

## 与其它模块

| 模块 | 接入后关系 |
|------|------------|
| 我的实例 | `attId` 过滤通话；概览已留「通话能力」说明 |
| 回拨任务 | 通话失败/转人工可生成回拨（后端写；前端已有 mock 演示） |
| 预约结果 | 通话中预约工具的结果展示 |
| 工作台 | 指标区标注「演示」直至 stats 接通 |

## 明确不做（Admin 内）

- 浏览器软电话 / WebRTC 拨号盘  
- 伪造「已接通」通话列表冒充真系统（工作台曲线除外且标明演示）  
