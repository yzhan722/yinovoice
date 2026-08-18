# TASKS

## Voice Agent Instance 产品化

- [x] A1：租户实例列表 API、真实 UUID 选择、助手列表/实时通话/知识库配置接入
- [x] A2：实例新建 API、服务端校验、前端表单及受保护的合成演示数据初始化函数
- [x] A2 表单：打开时预填合成演示默认文案（可编辑）
- [x] Stage1：构建 `/stage1` 前端并用 `scripts/deploy_stage1_isolated.py` 部署到 `/opt/yino-vapi-stage1`（不动生产）
- [x] Stage1：独立库 `yino_platform_stage1` + 迁移；实例/通话记录持久化冒烟通过（生产库未改）
- [ ] Stage1 网页冒烟：列表、新建非空实例、配置页、通话记录页（接口侧已可；请浏览器确认）
- [ ] Stage1 验收相关改动：由用户在 GitHub Desktop 自行分批 commit / push（治理 / A1 / A2 / 通话记录 CRUD / Stage1 脚本）
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

- [ ] C 后续：真实预约系统（指定医生、项目时长、档期冲突判断）
- [ ] SIP / 电话通道  
- [ ] 生产多租户与 RBAC（替换 Demo `X-Tenant-ID`）  
- [ ] 按需纳入 archive 原型（单独确认）  
