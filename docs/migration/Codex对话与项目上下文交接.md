# Codex 对话与项目上下文交接

更新日期：2026-08-25

## 文档性质

这是本次迁移协作对话的脱敏、结构化摘要，不是逐字聊天存档。对话附件和原始工具输出只能作为核对材料；仓库事实以代码、Git 状态和治理文件为准。本文件不记录密钥、Token、密码、客户联系方式、患者信息、录音地址或正式连接串。

## 仓库与权限上下文

- 仓库所有者：`yzhan722`。
- 仓库：`yzhan722/yinovoice`，私有仓库。
- 本地目录：`E:\Repos\yinovoice`。
- 预期 `origin`：`https://github.com/yzhan722/yinovoice.git`。
- 当前使用者是获得授权的协作者，不需要等于仓库所有者，也不应被要求切换到所有者账号。
- 只需确认协作者拥有目标操作所需权限。GitHub Desktop 登录账号仍需在 `File → Options → Accounts` 人工确认。
- 自动化助手不得自行 commit、push、强制推送、创建 PR、部署、删除远程内容或修改仓库权限/可见性。

## 对话过程摘要

1. 初次只读检查时，目标本地仓库只有根 `.git`，本地和远程均无提交或文件。
2. 第一阶段报告因此保存在仓库外临时目录，没有写入空仓库。
3. 用户随后完成内容迁移；复核时仓库已有 522 个文件和本地提交 `d88ee92`。
4. 迁移内容未包含源仓库 Git 历史，也未嵌套源 `.git`。
5. 用户授权第二阶段自动修正文档和协作规则，但继续禁止删除文件、修改业务逻辑和远程 Git 写操作。
6. 中文文档经字节级检查是有效 UTF-8；此前乱码来自 PowerShell 默认显示编码，不应批量转码。
7. 本轮建立统一索引、状态、决策、任务、安全、协作规则和最终验收入口。

## 项目理解

YINO AI Voice 是多租户 AI 电话客服平台。当前可运行主链路为浏览器、LiveKit、Runtime Voice Agent 与 Qwen Realtime。Control Plane 管理配置、通话记录和管理界面；Platform Core 提供知识、Prompt、Policy、Tool 和 Provider 抽象；RAGFlow 等外部系统通过集成层连接。

## 不可变架构原则

1. Yino 是业务数据和配置的唯一事实来源。
2. Vapi 是执行适配器、兼容渠道和备用渠道。
3. Vapi Workflows 不是核心依赖。
4. n8n 仅负责异步自动化，不进入实时通话主链路。
5. 后续运行时方向是 LiveKit Agents 与 SIP。
6. 配置发布支持版本、校验、回读、Diff、测试和回滚。
7. 通话录音转存至 Yino 控制的 S3 兼容存储。
8. 客户数据迁移可审计、可回滚。
9. Customer、Agent、Conversation 和 Usage 等数据由 Yino 管理。
10. 外部平台不能成为 Yino 业务数据的唯一存储位置。

## 当前模块

- `apps/control-plane/api`：FastAPI Control Plane、领域模型、repository、PostgreSQL/Alembic、LiveKit token 和通话记录。
- `apps/control-plane/web`：Vue 3/TDesign 管理与客户界面、实时语音、转写和通话记录。
- `apps/runtime/voice-agent`：LiveKit Agents、Qwen Realtime、DashScope/Fun-ASR 和会话运行时。
- `packages/platform-core`：平台中立的知识、Prompt、Policy、Tool 和 Provider 抽象。
- `integrations`：RAGFlow 与示例模板/实例。
- `deploy`、`scripts`：部署快照、本地与服务器运维脚本。
- `docs`：ADR、PRD、研究、设计、计划、测试和迁移记录。

## 已知未决事项

- `deploy/src` 与 `apps` 存在重复快照，尚未决定去重方式。
- 部分脚本可能仍引用迁移前目录名。
- 完整 Vapi Adapter、生产多租户/RBAC、真实 PSTN/Egress 和配置发布闭环仍未完成。
- 商业闭环（内建排期、Tool、挂断抽取按档期写入、SMTP、排期页通知设置）已在 `apps/` 落地；真实电话暂缓。未部署生产。
- 三个已跟踪 `*.egg-info` 生成目录是否移除，需要单独确认。
- rulesets/branch protection 是否强制 PR，需要仓库所有者或管理员确认。

## 后续对话交接方法

新对话应先阅读 `README.md`、`CONTEXT.md`、`PROJECT_STATUS.md`、`DECISIONS.md`、`TASKS.md`、`AGENTS.md` 和本文件。对话中形成稳定决策后更新 `DECISIONS.md`；状态变化更新 `PROJECT_STATUS.md`；未完成工作更新 `TASKS.md`。不要持续追加逐字聊天流水。
