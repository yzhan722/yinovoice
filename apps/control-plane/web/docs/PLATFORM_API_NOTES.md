# Platform Core API 契约备忘（壳 stub）

当前 `apps/admin` 仍调用旧 AVM 路径风格（`api/admin/*`、`api/user/*`）。对接 YinoVapi Platform Core 时建议演进为：

## 建议资源

| 资源 | 方法意图 | 备注 |
|---|---|---|
| `/api/operator/tenants` | CRUD 租户 | 替代 `api/admin/user/*` |
| `/api/operator/templates` | 发布/停用模板版本 | 新增 |
| `/api/tenants/{id}/instances` | 从模板创建/列表实例 | 替代 `assistant/*` |
| `/api/tenants/{id}/knowledge` | 上传/发布知识库 | 保留上传流，补版本 |
| `/api/tenants/{id}/calls` | Call Record 列表/详情 | 替代 `call-history` |
| `/api/tenants/{id}/callback-tasks` | 回拨任务 | 新增 |
| `/api/operator/providers` | Provider / 区域准入 | 新增；禁止前端直连厂商 sync |

## 迁移原则

1. 前端先改文案与菜单，path/service 名可第二步批量替换。
2. 厂商同步只出现在 Provider Adapter 服务端；UI 不暴露 `syncAssistants`。
3. Operator 默认不可读 Tenant 完整通话正文（PRD 5.1）。
4. 通话系统单独 share 时，只改 `TenantCallRecordService` + `VITE_CALL_SYSTEM_READY`（见 `CALL_INTEGRATION.md`）。

## 本地开发

`.env.development`：

```env
VITE_BASE_API=http://127.0.0.1:8086/
VITE_BASE_URL=/
VITE_SHELL_MOCK=true
VITE_CALL_SYSTEM_READY=false
```

在 Core API 就绪前，页面会 401/网络失败属预期；壳以 `bun run typecheck` + `bun run dev` 可启动为准。
