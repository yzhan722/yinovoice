# yinovoice 文档索引

本页是仓库文档的稳定入口。当前事实以 `PROJECT_STATUS.md` 为准，稳定架构决策以 `DECISIONS.md` 为准，未完成事项以 `TASKS.md` 为准。

## 根目录治理文件

| 文件 | 用途 |
|---|---|
| `README.md` | 项目入口、组件、开发与测试命令 |
| `CONTEXT.md` | 平台领域术语与统一语言 |
| `AGENTS.md` | Codex 的调查、修改、验证和交付边界 |
| `PROJECT_STATUS.md` | 当前已验证状态与已知限制 |
| `DECISIONS.md` | 稳定架构与迁移决策 |
| `TASKS.md` | 待办与人工确认事项 |
| `SECURITY.md` | 密钥、隐私、录音和报告安全规则 |
| `CONTRIBUTING.md` | 人工协作、提交和审查流程 |
| `.cursor/rules/project-rules.mdc` | Cursor 代码生成与编辑约束 |

## 主题文档

- `docs/realtime/`：LiveKit SIP inbound Stage runbook、A→B lookup 契约变更请求、Egress/usage/lookup 鉴权、2026-09-01 Live SIP E2E 结果、2026-09-02 Runtime hardening 与 Voice UX results（SYNTHETIC）、conversation runtime map、Voice UX timer 契约请求。
- `docs/architecture/`：当前架构说明。
- `docs/platform/`：平台规格、设计和实施计划。
- `.github/workflows/ci.yml`：api / voice-agent / web / call-insights / contracts 分 Job。
- `packages/contracts/ended-call/`：Yino → Insights ended-call v1 schema 与 fixtures。
- `docs/platform/superpowers/specs/2026-08-24-commercial-mvp-inbound-voice-design.md`：入站电话商业 MVP 设计。
- `docs/platform/superpowers/plans/2026-08-24-commercial-mvp-inbound-voice.md`：入站电话实施计划。
- `docs/platform/2026-09-01-industry-demo-scenarios.md`：7 个合成行业语音案例与试话。
- `docs/platform/2026-08-18-stage1-capability-report.md`：Stage1 能力范围汇报（已交付 / 边界 / 演示剧本）。同目录有 `.html` / `.docx` 导出稿。
- `docs/source-root/`：迁移源中的 ADR、PRD、研究、测试协议与历史计划。
- `docs/operations/`：运行和维护说明。
- `docs/security/`：专题安全文档。
- `docs/migration/`：迁移盘点、路径映射、复核、验收和 GitHub Desktop 操作说明。

## 迁移与交接入口

- `docs/migration/Codex对话与项目上下文交接.md`
- `docs/migration/Codex复核报告.md`
- `docs/migration/敏感信息检查报告.md`
- `docs/migration/目录调整建议.md`
- `docs/migration/GitHub入库建议.md`
- `docs/migration/待确认修改清单.md`
- `docs/migration/最终验收报告.md`
- `docs/migration/GitHub-Desktop操作说明.md`

## 维护规则

- 新增长期文档时更新本索引。
- 不把原始聊天、客户材料、录音、正式配置或账户导出文件作为项目文档提交。
- 历史文档不因过时直接删除；在当前状态或索引中标明其历史属性和替代入口。
