# CONTRIBUTING

## 协作方式

- 仓库所有者：`yzhan722`  
- 协作者可通过 GitHub Desktop / git 向本仓库贡献  
- 默认不要强推、不要改写远程历史、不要修改仓库可见性或协作者名单  

## 开发流程建议

1. 从最新 `main` 更新本地克隆  
2. 需要时创建功能分支  
3. 本地验证（测试 / Demo 冒烟）  
4. 确认 `git status` 无敏感文件  
5. 通过 GitHub Desktop 提交；按权限直接推送或开 PR  

首次迁移或跨模块大改默认使用新分支和 Pull Request。拥有直接推送权限不等于应绕过审查；是否强制 PR 以仓库 rulesets/branch protection 为准。

## 代码与文档

- 遵循 `AGENTS.md` 架构边界与 `SECURITY.md`  
- 客户数据与录音不得进入 PR  
- 重要决策写入 `DECISIONS.md`，状态写入 `PROJECT_STATUS.md` / `TASKS.md`  

## 安全检查清单（提交前）

- [ ] 无 `.env`（除 `.env.example`）  
- [ ] 无录音与导出隐私数据  
- [ ] 无 `node_modules` / `.venv` / 大日志  
- [ ] 无嵌套 `.git`  

## 提交拆分建议

- 治理、规则和文档索引
- Control Plane API 与数据模型
- Runtime、LiveKit Agents 与 SIP
- Vapi Adapter、API/Webhook 与外部集成
- 部署、测试和 CI
- 脱敏知识库与业务说明

不要为了拆分而修改业务逻辑；每个提交应能独立说明目的和验证结果。
