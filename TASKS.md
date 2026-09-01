# TASKS

## 两人并行 Sprint 1（2026-08-31）

- [x] B0 / B-S1.1：Call Insights 迁入 `apps/call-insights`（本工作树；未 commit）
- [x] B-S1.2：根 CI baseline + `scripts/test_all.ps1` + ended-call 契约 fixtures
- [x] B-S1.3：号码绑定 inbound lookup 产品化测试（E.164 / 租户隔离 / 无 secret 字段；增强现有 API，未新建重复模型）
- [x] B-S1.4：预约 modify 冲突 + cancel 幂等 + 禁止修改已取消预约
- [ ] B 短任务合回 `dev/platform-insights`（需用户授权 commit/push）
- [x] DEV-A LiveKit SIP inbound adapter（模拟 E2E / 模板 / 只读 preflight；未真实拨号）
- [x] DEV-A 国内 SIP 送号归一化（0519/010/400/11 位手机 → E.164；未真实拨号）
- [x] DEV-A LiveKit Egress → S3 客户端（RoomComposite audio/OGG；缺 S3 则关闭；CI 不连真实桶）
- [x] DEV-A `response.done` usage 入账（finish JSON + `call_records.usage`）
- [x] lookup 鉴权归控制面（`X-Phone-Lookup-Token`；空 token 401）
- [ ] DEV-A Live SIP Stage E2E → `LIVE_SIP_E2E_PASS`（2026-09-01 停在 **NEEDS_LIVEKIT_PROVISIONING**：无凭据、无 worker、trunk/DID/dispatch 未在本机可见）
- [ ] Integrator 验收后再合 `main`

## 商业 MVP 入站电话闭环（2026-08-25）

- [x] M1：E.164 号码映射、lookup、SIP dry-run 生成器
- [x] M2：通话会话 start/messages/finish（`in_progress`）
- [x] M3：内建单资源排期 + availability；停止编造预约时段
- [x] M4：Tool Invocation API + 幂等写
- [x] M5：Runtime 通话中 `[[tool:...]]` 旁路
- [x] M6：SIP 录音对象键 + LiveKit RoomComposite Egress 客户端（S3 配齐才启用；测试 mock）
- [x] M7：通知设置 + SMTP（配齐 host+from 走 smtplib；测试用 Fake sink）
- [x] M8：TDesign 电话/排期页、通话抽屉 Tool 记录、Dashboard 真实 KPI；排期页可保存通知邮箱
- [x] M9：`.env.example`、合成冒烟、手工 A–E 清单、治理文档对齐
- [x] 挂断抽取按诊所时区解析时段；无排期/无匹配项目/档期不可用则写回拨，不写假预约
- [x] Demo 操作员登录（HMAC token）+ 保留 `X-Tenant-ID` 给测试与 voice-agent；Bearer 与 Header 不一致则 403
- [x] 实例配置快照：创建自动基线、发布、Diff、按版本回滚（不拆 draft/live 调度）
- [x] 文本知识条目编译进 `tenant_prompt` 标记区；`.txt` 上传；不接 RAG / PDF
- [x] Call Insights 渠道契约（分仓时已落地；2026-08-31 起应用代码迁入 Monorepo，契约不重写）。代码完成，未部署、未 commit
- [x] Runtime 成功挂断调用 `finish`（等 LiveKit close / job shutdown；失败路径仍 `agent_error`）
- [ ] 真实 PSTN / LiveKit SIP trunk（代码已就绪；2026-09-01 真电话 E2E **BLOCKED**：缺 `.env.local`、worker、可见 trunk/DID/dispatch；未买号、未改资源）
- [x] LiveKit Egress → S3 客户端（仍需生产 S3/LiveKit Egress worker 与迁移 `20260901_0012`）
- [ ] 生产 SSO / 角色矩阵 / 计费（当前仅 Demo 操作员 HMAC 登录；voice-agent 仍可用 `X-Tenant-ID`）

## Voice Agent Instance 产品化

- [x] A1：租户实例列表 API、真实 UUID 选择、助手列表/实时通话/知识库配置接入
- [x] 实时语音页多实例切换（会话存储 + `instanceId` 查询同步；切换会重挂 LiveKit 面板）
- [x] 实时语音页可选 CosyVoice 音色（写入当前实例，下次通话生效）
- [x] 多行业合成演示案例（7 个虚构机构 + 排期/知识 + 导入接口；2026-09-01 已覆盖现站 `/opt/yino-vapi`）
- [x] A2：实例新建 API、服务端校验、前端表单及受保护的合成演示数据初始化函数
- [x] A2 表单：打开时预填合成演示默认文案（可编辑）
- [x] Stage1：构建 `/stage1` 前端并用 `scripts/deploy_stage1_isolated.py` 部署到 `/opt/yino-vapi-stage1`（不动生产）
- [x] Stage1：独立库 `yino_platform_stage1` + 迁移；实例/通话记录持久化冒烟通过（生产库未改）
- [ ] Stage1 网页冒烟：列表、新建非空实例、配置页、通话记录页（接口侧已可；请浏览器确认）
- [x] Stage1 验收相关改动：A3 + 预约/回拨 Phase1–2 已本地 commit `46066b7`（push 另授）
- [ ] A2 后续：在明确的本地/测试 PostgreSQL 环境运行演示数据初始化并做持久化冒烟验证
- [x] A3：实例停用或软删除（先明确通话记录和配置版本的保留策略）
- [x] B（部分）：通话记录软删除 CRUD（PUT/DELETE/restore + 网页删改）；搜索与完整审计仍待做
- [x] C：回拨与预约 — Phase1 网页真实化；Phase2 通话结束意向抽取（含姓名优先询问、列表「语音自动」）；真外呼 / 医生档期冲突引擎另期

## 立即（上传前）

- [x] 内容复制到 `E:\Repos\yinovoice`，未嵌套源仓库 `.git`
- [x] 只读确认无 `.env`（非 example）、无录音、无 `node_modules`、无 50 MB 以上文件
- [x] 本地已有首次迁移提交 `d88ee92`（非本轮 Codex 创建）
- [ ] 在 GitHub Desktop 的 `File → Options → Accounts` 人工确认登录账号
- [ ] 在 GitHub Desktop 中检查本轮文档变更和全部待提交文件
- [ ] 由所有者/管理员确认 rulesets、分支保护和是否强制 PR
- [ ] 使用新分支和 PR 完成首次远程审查；若决定直接推送，须由用户明确选择并自行操作

## 短期

- [x] 修正 `scripts/deploy_stage1_isolated.py` 相对路径以适配 monorepo（其它 scripts 仍待收敛）
- [ ] 修正其余 `scripts/` 相对路径以适配新 monorepo 布局  
- [ ] 收敛 `deploy/src` 与 `apps/` 重复代码  
- [ ] 补齐 `packages/vapi-adapter` 设计与占位实现  
- [x] 录音转 S3 兼容存储的设计落地（客户端已接；生产桶与 Egress worker 仍待配）  
- [ ] 生产 SSO / 角色矩阵 / 计费（当前仅 Demo 操作员 HMAC 登录）
- [x] 配置发布：版本 / 校验 / 回读 / Diff / 回滚  
- [ ] 决定是否移除已跟踪的三个 `*.egg-info` 生成元数据目录
- [ ] 决定 `deploy/src` 快照的长期保留、生成或去重策略

## 中期

- [ ] C 后续：多医生 / HIS 对接（当前商业 MVP 为单资源内建排期）
- [ ] SIP / 电话通道：生产 PSTN 与真实 Egress worker（代码映射与 Egress 客户端已在，不阻塞网页预约/回拨闭环）  
- [ ] 生产多租户与完整 RBAC（当前仅 Demo 操作员 HMAC；voice-agent 仍可用 `X-Tenant-ID`）  
- [ ] 按需纳入 archive 原型（单独确认）  
