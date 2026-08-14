# Stage1 隔离部署（yinovoice monorepo）

目标：把本地 `apps/`（含 A1/A2）部署到服务器 `/opt/yino-vapi-stage1`，入口 `https://<HOST>/stage1/`。  
**不覆盖**生产 `/opt/yino-vapi`。

设计见：`docs/platform/superpowers/specs/2026-08-13-stage1-monorepo-deploy-design.md`。

## 前置

本机已设置环境变量（不要写入 Git，不要在聊天中粘贴密码）：

```cmd
set BT_HOST=8.215.80.82
set BT_USER=root
set BT_PASSWORD=你的密码
```

本机已安装：Python（含 `paramiko`）、Node/pnpm。

## 1. 构建 Stage1 前端

```cmd
cd /d E:\Repos\yinovoice\apps\control-plane\web
set VITE_BASE_URL=/stage1/
set VITE_PLATFORM_API_BASE=/stage1
set VITE_SHELL_MOCK=true
set VITE_CALL_SYSTEM_READY=true
pnpm install --frozen-lockfile
pnpm build
```

确认存在：`E:\Repos\yinovoice\apps\control-plane\web\dist\index.html`。

## 2. 部署到 Stage1

```cmd
cd /d E:\Repos\yinovoice
py -3 scripts\deploy_stage1_isolated.py
```

脚本会：

- 打包 `apps/control-plane/api`、`apps/runtime/voice-agent`、`web/dist`
- 写入 `/opt/yino-vapi-stage1`
- 启动 `yino-platform-api-stage1` / `yino-voice-agent-stage1`
- 配置 nginx `/stage1` 前缀
- **不会**恢复或覆盖生产前端

## 3. 验收

浏览器：

- 生产：`https://8.215.80.82/#/login`（仍为原环境）
- Stage1：`https://8.215.80.82/stage1/#/login`（demo / demo123）
- Stage1 我的实例：`https://8.215.80.82/stage1/#/user/assistant-settings`

接口期望：

| 检查 | 期望 |
|------|------|
| 生产 `GET /api/v1/customer-services` | 404 |
| 生产 `POST /api/v1/customer-services` | 404 |
| Stage1 `GET /stage1/api/v1/customer-services` | 非 404（常为 200） |
| Stage1 / 生产相关 systemd | 均为 active |

Stage1 数据库（推荐配置）：

- 共用 Docker 容器 `yino-platform-postgres`
- **独立库名** `yino_platform_stage1`（不是生产库 `yino_platform`）
- 部署脚本会从生产 `DATABASE_URL` 改写库名、建库（若不存在）、执行 `alembic upgrade head`
- 实例表、通话记录表等与生产同结构，可在 Stage1 真实读写；不清空生产数据

新建表单带合成预填，可直接创建非空演示实例。

## 4. 回退 Stage1（不影响生产）

仅在需要时由运维执行：停止 Stage1 两个 systemd 服务，并移除 nginx 中 stage1 片段后 reload。生产目录与回滚备份保持不动。
