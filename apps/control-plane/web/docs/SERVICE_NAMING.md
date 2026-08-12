# Service naming map (CONTEXT)

Pages import from `@/api/platform`. Legacy `@/api/Admin*Service` files re-export for compatibility.

| Legacy | CONTEXT facade | Role |
|---|---|---|
| AdminUserService | OperatorTenantService | Platform Operator ↔ Tenant |
| AdminAssistantService | OperatorInstanceService | Platform Operator ↔ Voice Agent Instance |
| UserAssistantService | TenantInstanceService | Tenant ↔ Instance |
| AdminCallHistoryService | OperatorCallRecordService | Call Record |
| UserCallHistoryService | TenantCallRecordService | Call Record |
| AdminDashboardService | OperatorDashboardService | Dashboard (+ shell mock) |
| UserDashboardService | TenantDashboardService | Dashboard (+ shell mock) |
| AdminKnowledgeBaseService | OperatorKnowledgeService | Knowledge files |
| UserKnowledgeBaseService | TenantKnowledgeService | Tenant Knowledge Base |

HTTP paths remain `api/admin/*` / `api/user/*` until Platform Core replaces them.

Shell mock: set `VITE_SHELL_MOCK=true` (default in `.env.development`) so dashboards render without a backend.
