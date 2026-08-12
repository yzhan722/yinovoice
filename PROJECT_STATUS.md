# PROJECT_STATUS

更新日期：2026-08-12

## 总览

| 项 | 状态 |
|----|------|
| 目标仓库 | `yzhan722/yinovoice` |
| 本地克隆 | `E:\Repos\yinovoice` |
| 远程内容（整理前） | 空仓库 |
| 本轮动作 | 自本机/LAN **复制整理**（源项目未改、未嵌套 `.git`） |
| Git 提交/推送 | **未执行**（待 GitHub Desktop 人工处理） |

## 已纳入

- Control Plane API / Web / Runtime voice-agent（来自 stage1 worktree）  
- 根文档 `CONTEXT.md`、`docs/source-root`、`docs/platform`  
- LAN：`packages/platform-core`、`deploy/`、`integrations/`（已排除疑似正式 `.env` 与前端构建产物）  
- 协作文件：`README` / `AGENTS` / `SECURITY` / 等  

## 本轮未纳入（默认）

- `archive/` 原型（STT hello、fun-asr、web-console、ai-voice-management）  
- `livekit-server.exe`  
- 任何通话录音、真实 `.env`  
- 原 Git 历史（未做 subtree/历史合并）  

## 已知限制

- `scripts/` 部分路径可能仍假设旧目录名 `YinoVoicePlatform`  
- `deploy/` 含历史部署快照，需后续与 `apps/` 去重收敛  
- 推送权限未用 `gh` API 最终确认；以 Desktop 推送结果为准  
