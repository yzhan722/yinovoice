# AGENTS.md — Codex / Cursor 协作说明

## 项目目标

建设 YINO AI Voice：Yino 自管业务数据与配置；实时语音以 LiveKit Agents 为主路径；Vapi 仅作适配/兼容/备用。

## 技术栈

- Web：Vue 3、Vite、TDesign、livekit-client、pnpm
- Control Plane：Python、FastAPI、SQLAlchemy/asyncpg（可选）、LiveKit API
- Runtime：Python、livekit-agents、DashScope / Qwen Realtime
- 集成：RAGFlow 等（见 `integrations/`）
- 部署：Docker Compose、脚本（见 `deploy/`、`scripts/`）

## 架构边界（必须遵守）

1. Yino 是业务数据与配置的唯一事实来源  
2. Vapi 是执行适配器、兼容渠道和备用渠道  
3. 不把 Vapi Workflows 作为核心依赖  
4. n8n 只负责异步自动化，不进入实时通话主链路  
5. 后续运行时方向为 LiveKit Agents 与 SIP  
6. 配置发布必须支持版本、校验、回读、Diff、测试和回滚  
7. 通话录音应转存到自有 S3 兼容存储  
8. 客户数据迁移必须可审计、可回滚  
9. Customer / Agent / Assistant / Conversation / Usage 由 Yino 自管  
10. 外部语音平台不得成为业务数据的唯一存储位置  

## 目录说明

| 路径 | 说明 |
|------|------|
| `apps/control-plane/` | API + Web |
| `apps/runtime/` | voice-agent |
| `packages/` | 可复用库（如 platform-core） |
| `integrations/` | 外部系统模板 |
| `deploy/` | 部署包（无真实密钥） |
| `docs/` | 文档与迁移报告 |
| `scripts/` | 本地脚本 |

## 安装 / 开发 / 测试命令

见根 `README.md`。优先使用 **CMD** 给出启动说明。

## 修改前检查

- 确认改动落在正确 app/package，不破坏架构边界  
- 不读取、不提交真实 `.env`  
- 不引入客户隐私或录音文件  
- API 变更考虑兼容与多租户隔离  

## 修改后验证

- 相关单元/集成测试  
- 本地 Demo 关键路径冒烟（若涉及通话链路）  
- `git status` 确认无密钥/录音/依赖目录  

## 隐私和密钥规则

- 密钥只存在本机 `.env.local` 或安全密钥管理  
- `.env.example` 仅变量名与安全占位  
- 日志脱敏；禁止把 Key 打进前端 `VITE_*`  

## 禁止事项

- 自动 `git push` / 强制推送 / 改写远程历史  
- 自动部署到生产  
- 嵌套其他 Git 仓库的 `.git`  
- 上传录音、患者/客户隐私、正式环境配置  

## Git 操作边界

- 默认由人工通过 GitHub Desktop 提交与推送  
- Agent 未经明确要求不得 commit / push / 建 PR  

## 完成标准

- 变更有对应验证  
- 文档与 `PROJECT_STATUS.md` / `TASKS.md` 必要时更新  
- 无敏感文件进入暂存区  

## 部署注意事项

- `deploy/config/*.env` 真实文件不得入库  
- 生产密码与 Token 必须轮换且与仓库隔离  
