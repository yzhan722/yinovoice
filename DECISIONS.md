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
| 通道 | LiveKit SIP inbound Runtime adapter 已落地（participant → lookup → 既有 session）。**本期仍不拨真实 PSTN**；买号/改 trunk/dispatch 需单独授权 |
| 排期 | Yino 内建单资源，不接 Google Calendar / HIS |
| 转接 | 不提供通话中转人工；只建回拨任务 |
| 通话中写 | 隐藏 `[[tool:...]]` 旁路；业务错误 HTTP 200 + `status=error` |
| 挂断抽取 | 诊所时区解析时段；档期不可用或不完整则回拨，不写假预约 |
| 录音 | 网页本地上传不变；SIP 在 S3+LiveKit 配齐后走 RoomComposite → S3（OGG）；缺 S3 则关闭。失败不挂断通话 |
| 对账 | `response.done` usage 累加后写入 `call_records.usage`（可选 JSON） |
| 入站 lookup | `GET /api/v1/phone-numbers/lookup` 必须 `X-Phone-Lookup-Token`；空 token 一律 401 |
| 通知 | 配齐 `SMTP_HOST` + `SMTP_FROM` 才发信（smtplib）；失败不回滚业务 |
| 身份 | Demo 操作员 HMAC 登录（`demo`/`demo123`）；测试与 voice-agent 仍可用 `X-Tenant-ID`；不做计费/角色矩阵 |
| 部署 | 不自动部署生产；未经用户授权不 commit / push |

## 2026-09-01 LiveKit SIP inbound Runtime

| 决策 | 内容 |
|---|---|
| Provider | Runtime provider 固定为 `livekit_sip`；Twilio/Telnyx 只是上游 |
| 路由 | 仅用 `sip.trunkPhoneNumber`（callee）查 Platform；禁止 fallback 到 caller |
| 国内送号 | Runtime 将 0 开头固话、400/800/95、11 位手机收成 `+86…` 再 lookup；Yino 绑定仍写 E.164 |
| Job metadata | 非空走既有 Platform dispatch；空 metadata + SIP kind 才走 inbound lookup |
| Dispatch Rule | 长期复用 individual + `LIVEKIT_AGENT_NAME`；规则里 agent metadata 必须为空；首测 `hide_phone_number=true` |
| 等待参与者 | 生产（未开 local-dev 空 metadata）只等 SIP kind=3，避免网页参与者抢先跳过 callee lookup |
| 去重 | 生产路径不做进程内 seen-call-id set；exactly-once 仍由 lifecycle `/finish` 保证 |
| 失败 | lookup 无 token / 401 / 404 / disabled / timeout / 5xx 全部 fail closed，不得进入 local default agent |

## 2026-08-31 Monorepo 合仓与两人并行分支

| 决策 | 内容 |
|------|------|
| 合仓 | Call Insights 真正应用迁入 `apps/call-insights`；Git 主仓为 `yzhan722/yinovoice` |
| 运行时 | 合仓 ≠ 合并进程或数据库。Yino API（Python/PostgreSQL）与 Insights（Node/SQLite）继续独立；异步 HTTP `POST /v1/ingest/:profile` 故障边界保持 |
| 旧分仓 | 2026-08-25「必须保持独立 Git 仓库」已被本决策替代（superseded），不是删除旧仓 |
| 长期分支 | `dev/realtime-telephony`（DEV-A）与 `dev/platform-insights`（DEV-B）从同一 `main` SHA 创建；日常 feat 从对应 `dev/*` 开出，不直接从 `main` 开 |
| CI | 根 `.github/workflows/ci.yml` 按 api / voice-agent / web / call-insights / contracts 分 Job；禁止真实 secrets 与生产网络 |
| 未做 | 不删除/归档 `vapi-call-insights` 旧仓；不部署 Stage/Production；不切真实 PSTN |

## 2026-08-25 Call Insights 渠道契约

| 决策 | 内容 |
|------|------|
| 分仓 | **superseded 2026-08-31**：应用代码并入 `yinovoice` Monorepo；独立仓库不再作为长期方向。契约、进程与数据库边界不变 |
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

