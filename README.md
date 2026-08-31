# yinovoice

YINO AI Voice（Yino Voice）主仓库：以 Yino 为业务与配置的唯一事实来源，Vapi 仅作为执行适配器/兼容与备用渠道；当前可运行主链路为 **浏览器 → LiveKit → Runtime Agent（Qwen Realtime）**。

## 当前系统定位

- **阶段**：从本地/LAN Demo 与 Vapi 迁移研究，收敛到可长期协作的 monorepo。
- **已落地**：Control Plane API、Runtime voice-agent、Vue 管理/通话前端、商业闭环（内建排期、通话中 Tool、诚实挂断抽取、SMTP 通知、TDesign 排期/电话页）。真实 PSTN 暂缓。
- **未完成/规划中**：生产级多租户与 RBAC、真实 PSTN/Egress、配置发布 Diff/回滚、完整 Vapi Adapter。

## 主要组件

| 路径 | 角色 |
|------|------|
| `apps/control-plane/api` | Platform API（配置、LiveKit token、Demo 通话记录、排期/回拨、Insights 投递） |
| `apps/control-plane/web` | 主前端（Vue 3 + Vite + TDesign） |
| `apps/runtime/voice-agent` | LiveKit Agent / Qwen Audio Realtime（独立 Python 进程） |
| `apps/call-insights` | Call Insights（独立 Node/Fastify 进程，SQLite；不在实时通话关键路径） |
| `packages/platform-core` | 知识库等平台核心适配（来自 LAN 增量） |
| `packages/contracts/ended-call` | Yino → Insights ended-call v1 共享契约与 fixtures |
| `integrations/` | 外部系统集成模板（如 RAGFlow） |
| `deploy/` | 部署包与运维脚本（不含真实密钥） |
| `docs/` | 架构、迁移、平台文档 |
| `scripts/` | 本地启动与辅助脚本 |

## Vapi 在系统中的定位

- Vapi = **适配器 / 兼容渠道 / 备用渠道**，不是业务数据主库。
- **不**把 Vapi Workflows 当作核心依赖。
- n8n 只做异步自动化，不进入实时通话主链路。
- 后续运行时方向：LiveKit Agents + SIP。

## 目录作用

详见 `AGENTS.md`。协作状态见 `PROJECT_STATUS.md`、`TASKS.md`、`DECISIONS.md`。

## 本地开发（CMD）

路径已从旧 `YinoVoicePlatform/` 调整到本仓库布局。示例：

```cmd
cd /d E:\Repos\yinovoice\apps\control-plane\api
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
copy .env.example .env.local

cd /d E:\Repos\yinovoice\apps\runtime\voice-agent
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
copy .env.example .env.local

cd /d E:\Repos\yinovoice\apps\control-plane\web
pnpm install --frozen-lockfile
copy .env.example .env.local
```

一键脚本仍在 `scripts\`，部分内部相对路径可能仍指向旧布局；若失败请按上表分窗口手动启动，或先阅读 `docs/platform/`。

需要本机 `livekit-server` 在 PATH 中；LiveKit `--dev` 的 `devkey`/`secret` **仅限本机**。

## 测试

```cmd
cd /d E:\Repos\yinovoice\apps\control-plane\api
.venv\Scripts\python.exe -m pytest

cd /d E:\Repos\yinovoice\apps\runtime\voice-agent
.venv\Scripts\python.exe -m pytest

cd /d E:\Repos\yinovoice\apps\control-plane\web
pnpm test
pnpm typecheck
pnpm build

cd /d E:\Repos\yinovoice\apps\call-insights
npm ci
npm test
npm run typecheck
```

Windows 一键入口：`powershell -ExecutionPolicy Bypass -File scripts\test_all.ps1`。

GitHub Actions 在 `.github/workflows/ci.yml` 按服务分 Job（不使用真实 secrets / SMTP / VAPI / DeepSeek / 生产库）。

合仓不等于运行时合并：Yino API 仍是 Python + PostgreSQL；Call Insights 仍是 Node + SQLite；两者只通过 `POST /v1/ingest/:profile` 异步联通。

## 文档入口

- 平台说明：`docs/platform/`
- 历史根文档：`docs/source-root/`
- 迁移报告：`docs/migration/`
- 当前项目上下文与对话交接：`docs/migration/Codex对话与项目上下文交接.md`
- 文档索引：`docs/README.md`
- 术语：`CONTEXT.md`
- 安全：`SECURITY.md`

## 当前项目状态

见 `PROJECT_STATUS.md`。本仓库由本机 Demo / worktree / LAN 增量整理而来；**原项目 Git 历史未并入**。当前本地已有首次迁移提交；是否已发布到远程必须以 `git ls-remote origin` 或 GitHub 页面为准。

## 安全边界 / 不得上传

- 真实 `.env`、API Key、Token、Cookie、数据库/S3 正式凭证
- 客户隐私、医疗/患者资料、合同发票、财务资料
- 真实或 Demo 通话录音（应转存自有 S3 兼容存储，不进 Git）
- `node_modules`、`.venv`、构建产物、超大日志与数据库备份

详见 `SECURITY.md`。
