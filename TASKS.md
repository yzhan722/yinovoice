# TASKS

## 立即（上传前）

- [ ] 在 GitHub Desktop 中检查 `E:\Repos\yinovoice` 变更列表  
- [ ] 确认无 `.env`（非 example）、无录音、无 `node_modules`  
- [ ] 人工首次 commit + push 到 `yzhan722/yinovoice`（账号 `Zezeyu01`）  
- [ ] 若 push 被拒：请所有者授予写权限或改走分支/PR  

## 短期

- [ ] 修正 `scripts/` 相对路径以适配新 monorepo 布局  
- [ ] 收敛 `deploy/src` 与 `apps/` 重复代码  
- [ ] 补齐 `packages/vapi-adapter` 设计与占位实现  
- [ ] 录音转 S3 兼容存储的设计落地  
- [ ] 配置发布：版本 / 校验 / 回读 / Diff / 回滚  

## 中期

- [ ] SIP / 电话通道  
- [ ] 生产多租户与 RBAC（替换 Demo `X-Tenant-ID`）  
- [ ] 按需纳入 archive 原型（单独确认）  
