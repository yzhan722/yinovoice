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
| `apps/runtime/` | voice-agent（Realtime；DEV-A） |
| `apps/call-insights/` | Call Insights 独立服务（DEV-B） |
| `packages/` | 可复用库（platform-core）与共享契约 `packages/contracts` |
| `integrations/` | 外部系统模板 |
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

## 文件命名与归档

- 代码遵循所在语言和模块的既有命名；文档使用能够直接表达主题的名称。
- 日期型计划、规格和迁移记录使用 `YYYY-MM-DD-主题.md`；长期入口文件保持稳定文件名。
- 不通过复制文件名后缀（如 `final`、`new`、`copy`）制造版本；版本变化写入 Git、状态或决策记录。
- 仍在构建、部署、测试或引用的内容不得放入 `archive`。
- 归档前记录来源、最后有效状态、替代路径和恢复方法；未经确认不得移动或删除旧文件。

## 数据库迁移规范

- 使用 Alembic 等可审阅迁移机制；迁移必须具备明确升级路径和可行的回滚/恢复方案。
- 禁止直接对生产数据库执行未经备份、评审和验证的破坏性操作。
- 模式变更应考虑多租户隔离、向后兼容、数据回填、审计和重复执行安全性。
- 测试与示例只使用合成数据，不复制生产库、客户或患者数据。

## 状态、任务和决策更新

- 当前事实写入 `PROJECT_STATUS.md`，未完成工作写入 `TASKS.md`，稳定决策写入 `DECISIONS.md`。
- 项目入口或目录变化同步更新 `README.md` 与 `docs/README.md`。
- 对话中的重要信息先脱敏，再更新 `docs/migration/Codex对话与项目上下文交接.md`；原始聊天不是事实来源。
- 报告不得包含客户隐私、患者信息、录音地址、完整凭据或正式连接串。

## Codex 与 Cursor 边界

- Codex 负责调查、风险复核、跨文件一致性、验证和交付报告；修改前先核对 Git 状态与用户已有变更。
- Cursor 主要负责交互式代码生成和局部编辑，并遵守 `.cursor/rules/project-rules.mdc`。
- 两者均不得自行扩大范围、修改业务边界、删除数据、推送、发布或部署。
- 发现不确定分类、敏感候选、远程规则不明或用户变更冲突时，记录到待确认清单，不猜测。

## Git 提交规范

- 推荐提交主题使用 `docs:`、`chore:`、`feat:`、`fix:`、`test:` 等清晰前缀，并保持单一目的。
- 大迁移按治理文档、核心模块、适配器/集成、部署测试和脱敏资料拆分。
- 未经用户对具体动作明确授权，不得 stage、commit、push、创建 PR、合并或发布。
- 禁止强制推送和改写远程历史；不得自动修改仓库权限、可见性和保护规则。

## 部署注意事项

- `deploy/config/*.env` 真实文件不得入库  
- 生产密码与 Token 必须轮换且与仓库隔离  
