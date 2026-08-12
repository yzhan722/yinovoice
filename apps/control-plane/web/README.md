# YinoVapi Admin Console

从旧项目 ai-voice-management 迁入的 Vue 3 + Vite + TDesign + Pinia 管理后台。

## 定位

- **保留**：Platform Operator / Tenant 双端运营台骨架与实例配置页面；
- **已接入 Demo**：Tenant“实时语音”、增量字幕/状态、网页语音记录，以及 Tenant /
  Operator 通话列表与 final transcript 详情；
- **规划中**：电话、预约、知识库仍是演示框架，未接入实时语音链路。

## 开发

~~~powershell
Copy-Item .env.example .env.local
pnpm install --frozen-lockfile
pnpm run dev
~~~

默认端口 3003，VITE_PLATFORM_API_BASE 默认指向本地 http://localhost:8000。
浏览器只向 Platform API 请求短期 LiveKit token，前端环境中不得放置 LiveKit 或
DashScope secret。

## Demo-only 限制

- 网页通话记录由浏览器在结束/中断时写入 Platform API，不是权威电话 CDR；
- Platform API 当前只使用内存仓库，服务重启后记录全部丢失；
- Operator 页面使用 .env.example 中配置的 Demo tenant header，仅供联调查看，
  不代表全局生产 RBAC；
- 只保存 final transcript；partial 字幕仅存在于当前页面；
- 电话、预约、知识库均未接通，页面会明确标为“规划中 / 演示框架”。

## 验证

~~~powershell
pnpm test
pnpm run typecheck
pnpm run build
~~~

## 目录约定

~~~text
front/          ← 本管理台
docs/           ← 产品 PRD / ADR（仓库根）
CONTEXT.md      ← 领域术语
~~~
