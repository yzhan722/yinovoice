# Admin 信息架构（第一阶段 Demo）

目标：**路径 A（电话优先）** — 通话 API 接入位就绪；工作台/回拨/预约可演示；知识库菜单靠后。

| 角色 | 菜单 | 路由 | 说明 |
|---|---|---|---|
| Tenant | 工作台 | `/user/dashboard` | 通话演示指标 + 待办 |
| Tenant | 我的实例 | `/user/assistant-settings` | 预置「太平洋口腔 · 新北前台」（常州太平洋口腔） |
| Tenant | 创建实例 | `/user/create-instance` | 侧栏隐藏 |
| Tenant | 回拨任务 | `/user/callback-tasks` | shell mock，默认可筛待处理 |
| Tenant | 预约结果 | `/user/appointments` | shell mock |
| Tenant | 通话记录 | `/user/call-history` | **API 预留**；`VITE_CALL_SYSTEM_READY` |
| Tenant | 知识库 | `/user/knowledge-base` | 菜单最靠下；mock |

## 演示剧本

见 [`DEMO_PATH_A.md`](./DEMO_PATH_A.md)。

## 通话一键接入

```env
VITE_CALL_SYSTEM_READY=true
VITE_CALL_API_BASE=http://<call-host>/
```

详见 [`CALL_INTEGRATION.md`](./CALL_INTEGRATION.md)。

## 刻意不做

- 真实 SIP / 实时语音
- 运营端完整菜单演示
- 通话统计大盘
- UI 暴露厂商 sync
