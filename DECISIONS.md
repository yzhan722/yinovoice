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
