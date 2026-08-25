# DECISIONS

## 已确认架构原则

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

## 2026-08-12 迁移决策

| 决策 | 内容 |
|------|------|
| 主源 | `E:\YinoVapi\.worktrees\yino-voice-stage1\YinoVoicePlatform` |
| 目标布局 | `apps/control-plane/*`、`apps/runtime/voice-agent` |
| LAN 增量 | 纳入 platform-core、deploy、integrations |
| archive 原型 | 本轮不纳入 |
| livekit-server.exe | 本轮不纳入 |
| 历史合并 | 不带入源仓库 Git 历史；不嵌套 `.git` |
| 工具 | 不依赖 gh CLI；由 GitHub Desktop 人工提交推送 |
| 密钥处理 | `deploy/config/*.env` 疑似正式配置已移出仓库至本机 quarantine |

## 2026-08-13 协作与对话迁移决策

| 决策 | 内容 |
|------|------|
| 对话迁移 | 不把原始聊天逐字提交；仅保存脱敏的事实、决策、约束和待办摘要 |
| 上下文入口 | `docs/migration/Codex对话与项目上下文交接.md` |
| 文档编码 | Markdown、规则与配置示例统一使用 UTF-8；终端乱码不等于文件损坏 |
| 首次入库 | 即使协作者有直接推送权限，也优先建议新分支与 Pull Request 审查 |
| 远程操作 | Codex/Cursor 不得自动 commit、push、建 PR、部署或修改权限，除非用户对具体动作另行明确授权 |
| 生成物 | `*.egg-info` 等生成元数据不应继续新增；现有已跟踪内容不在本轮删除 |

## 2026-08-25 商业 MVP 入站电话

| 决策 | 内容 |
|------|------|
| 通道 | LiveKit SIP 入站字段保留；**本期不接真实 PSTN**（Twilio 官方不支持大陆 +86 语音） |
| 排期 | Yino 内建单资源，不接 Google Calendar / HIS |
| 转接 | 不提供通话中转人工；只建回拨任务 |
| 通话中写 | 隐藏 `[[tool:...]]` 旁路；业务错误 HTTP 200 + `status=error` |
| 挂断抽取 | 诊所时区解析时段；档期不可用或不完整则回拨，不写假预约 |
| 录音 | 网页本地上传不变；SIP 走对象键 + Fake Egress；缺 S3 配置则关闭 |
| 通知 | 配齐 `SMTP_HOST` + `SMTP_FROM` 才发信（smtplib）；失败不回滚业务 |
| 身份 | Demo 操作员 HMAC 登录（`demo`/`demo123`）；测试与 voice-agent 仍可用 `X-Tenant-ID`；不做计费/角色矩阵 |
| 部署 | 不自动部署生产；未经用户授权不 commit / push |

## 2026-08-25 Call Insights 渠道契约

| 决策 | 内容 |
|------|------|
| 分仓 | Yino 与 Insights 保持独立仓库，不合并、不嵌套 `.git` |
| 入站 | Insights 保留 `POST /v1/vapi/:profile`；Yino 走独立 `POST /v1/ingest/:profile` + `INGEST_AUTH_TOKEN` |
| 绑定 | 助手 `insights_profile` 为空则不投递；未知 slug 由 Insights 4xx，Yino 记永久失败 |
| 邮件 | `channel=yino` 默认不建 mail outbox；仅 profile `mailEnabled: true` 才发。LucaPlus / INP JSON 不加该字段 |
| 挂断 | Yino 先保存通话/预约/回拨；Insights 失败不回滚。`recordingUrl` 恒为 null |
| Alembic | `20260825_0010` 已存在且 head 为 `0011`；不再另建冲突的 0010 |

## 2026-08-25 租户登录 / 配置发布 / 知识事实来源

| 决策 | 内容 |
|------|------|
| 登录 | 薄切片：stdlib HMAC token，绑定 Demo 租户；不引入 JWT 库、SSO、计费 |
| 租户头 | 有效 Bearer 取 token 内租户；仅 `X-Tenant-ID` 仍给测试与 Runtime；两者都有则必须一致 |
| 配置发布 | 当前实例行即通话配置；发布=快照；回滚=恢复快照并 bump `version`；创建时自动基线 |
| 知识 | 文本条目编译进 `tenant_prompt` 的 `<!-- yino-knowledge-* -->` 标记；不改 voice-agent 检索、不接 RAGFlow |

