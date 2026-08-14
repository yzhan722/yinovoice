# GitHub Desktop 操作说明

更新日期：2026-08-13

## 1. 确认账号

1. 打开 GitHub Desktop。
2. 进入 `File → Options → Accounts`。
3. 确认当前登录的是你自己的、已获 `yzhan722/yinovoice` 写权限的账号。
4. 不需要切换到仓库所有者 `yzhan722`。

本机 Git 凭据复核账号为 `Zezeyu01`，但仍必须以 GitHub Desktop 界面为准。

## 2. 选择仓库并获取状态

1. 选择本地仓库 `E:\Repos\yinovoice`。
2. 确认 Repository URL 为 `https://github.com/yzhan722/yinovoice.git`。
3. 点击 Fetch origin；不要使用 Force push。
4. 如果出现远程新历史、冲突或要求选择覆盖方向，停止操作并重新复核，不要强行继续。

## 3. 创建审查分支

建议从当前本地状态创建新分支，例如：

```text
codex/migration-governance-review
```

如果 GitHub Desktop 提示基于尚未发布的 `main` 创建分支，可继续创建本地分支，但推送前仍需检查全部 diff。

## 4. 审查 Changes

确认待提交内容只包括治理和迁移文档，例如：

- 根治理文件和 `.cursor` 规则；
- `.gitignore`；
- `docs/README.md`；
- `docs/migration/` 新增复核、交接和验收报告。

不应提交：

- `.env`、密钥、Token、Cookie、私钥或正式连接串；
- 客户联系方式、患者信息、真实录音或录音地址；
- `node_modules`、`dist`、虚拟环境、缓存、日志和数据库备份；
- 未经确认的原始聊天导出或附件。

验证时生成的 `apps/control-plane/web/node_modules` 和 `apps/control-plane/web/dist` 已被忽略，不应出现在 Changes 中。

## 5. 提交拆分

当前本地已有迁移基线提交 `d88ee92`。本轮建议单独使用治理提交，例如：

```text
docs: standardize migration governance and handoff
```

不要把后续脚本路径修复、部署去重或业务功能修改混入该提交。

## 6. 推送与 Pull Request

1. 本轮由用户在 GitHub Desktop 中人工 commit。
2. Publish branch/Push origin 前再次确认分支不是直接覆盖受保护的 `main`。
3. 推荐在 GitHub 上创建 Pull Request，由所有者或指定维护者审查。
4. 如果推送或 PR 被规则拒绝，请所有者确认 rulesets、审批数和 CI；不要请求切换到所有者账号，也不要强制推送。

Codex 未执行 commit、push 或创建 Pull Request。
