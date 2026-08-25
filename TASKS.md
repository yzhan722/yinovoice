# TASKS

## 商业 MVP 入站电话闭环（2026-08-25）

- [x] M1：E.164 号码映射、lookup、SIP dry-run 生成器
- [x] M2：通话会话 start/messages/finish（`in_progress`）
- [x] M3：内建单资源排期 + availability；停止编造预约时段
- [x] M4：Tool Invocation API + 幂等写
- [x] M5：Runtime 通话中 `[[tool:...]]` 旁路
- [x] M6：SIP 录音对象键 + Fake Egress（无真实 LiveKit Egress 客户端）
- [x] M7：通知设置 + SMTP（配齐 host+from 走 smtplib；测试用 Fake sink）
- [x] M8：TDesign 电话/排期页、通话抽屉 Tool 记录、Dashboard 真实 KPI；排期页可保存通知邮箱
- [x] M9：`.env.example`、合成冒烟、手工 A–E 清单、治理文档对齐
- [x] 挂断抽取按诊所时区解析时段；无排期/无匹配项目/档期不可用则写回拨，不写假预约
- [ ] 真实 PSTN / LiveKit SIP trunk（**已搁置**：先完成网页与后处理闭环；国内 +86 不能靠 Twilio）
- [ ] 真实 LiveKit Egress → S3
- [ ] 生产多租户登录与 RBAC（替换 Demo `X-Tenant-ID`）

## Voice Agent Instance 产品化

- [x] A1：租户实例列表 API、真实 UUID 选择、助手列表/实时通话/知识库配置接入
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
- [ ] 录音转 S3 兼容存储的设计落地  
- [ ] 配置发布：版本 / 校验 / 回读 / Diff / 回滚  
- [ ] 决定是否移除已跟踪的三个 `*.egg-info` 生成元数据目录
- [ ] 决定 `deploy/src` 快照的长期保留、生成或去重策略

## 中期

- [ ] C 后续：多医生 / HIS 对接（当前商业 MVP 为单资源内建排期）
- [ ] SIP / 电话通道：生产 PSTN 与真实 Egress（**暂缓**；代码映射与 Fake Egress 已在，不阻塞网页预约/回拨闭环）  
- [ ] 生产多租户与 RBAC（替换 Demo `X-Tenant-ID`）  
- [ ] 按需纳入 archive 原型（单独确认）  
