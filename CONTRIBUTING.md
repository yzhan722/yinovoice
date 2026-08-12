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

## 代码与文档

- 遵循 `AGENTS.md` 架构边界与 `SECURITY.md`  
- 客户数据与录音不得进入 PR  
- 重要决策写入 `DECISIONS.md`，状态写入 `PROJECT_STATUS.md` / `TASKS.md`  

## 安全检查清单（提交前）

- [ ] 无 `.env`（除 `.env.example`）  
- [ ] 无录音与导出隐私数据  
- [ ] 无 `node_modules` / `.venv` / 大日志  
- [ ] 无嵌套 `.git`  
