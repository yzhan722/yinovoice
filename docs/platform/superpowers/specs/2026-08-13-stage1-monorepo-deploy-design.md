# Stage1 Monorepo 隔离部署设计

日期：2026-08-13  
状态：已批准（含新建表单预填补充）  
仓库：`E:\Repos\yinovoice`（`yzhan722/yinovoice`）

## 目标

在 commit 之前，使当前 monorepo（含本地 A1/A2）可部署到服务器 **Stage1 隔离栈**，用于网页与接口验收；**不覆盖生产** `/opt/yino-vapi`。

## 补充需求：新建表单预填

Stage1 / 本地验收时，`InstanceCreateDialog` 打开后应带有**可编辑的合成演示默认值**，避免名称、机构、欢迎语、Platform/Tenant Prompt 一片空白导致创建出“空壳”实例。

要求：

- 默认填充：`display_name`、`organization_name`、`greeting`、`platform_prompt`、`tenant_prompt`（及现有音色默认）
- 内容仅为合成演示文案，不含真实客户/患者数据
- 用户仍可全部修改；创建失败时保留用户当前输入（既有 A2 行为不变）
- 不强制用户必须使用默认值；提交仍走现有 `POST /api/v1/customer-services`

## 非目标

- 不部署 A1/A2 到生产
- 不删除或覆盖生产回滚备份
- 不自动 `git commit` / `push` / 创建 PR
- 本轮不双写或同步 `deploy/src` 快照
- 不为 Stage1 接入**生产库名**；Stage1 使用同容器独立库 `yino_platform_stage1`

## 部署真源

| 组件 | 本地路径 | Stage1 远程路径 |
|------|----------|-----------------|
| Platform API | `apps/control-plane/api` | `/opt/yino-vapi-stage1/platform-api` |
| Voice Agent | `apps/runtime/voice-agent` | `/opt/yino-vapi-stage1/voice-agent` |
| 前端构建产物 | `apps/control-plane/web/dist`（构建后） | `/opt/yino-vapi-stage1/frontend-dist` |

不以 `deploy/src` 为部署源（该目录为历史快照，缺少 A1/A2）。

## 隔离边界

| 项 | 生产 | Stage1 |
|----|------|--------|
| 根目录 | `/opt/yino-vapi` | `/opt/yino-vapi-stage1` |
| 浏览器入口 | `https://8.215.80.82/` | `https://8.215.80.82/stage1/` |
| API 端口 | `127.0.0.1:8000` | `127.0.0.1:8011` |
| nginx API 前缀 | `/api/v1/` | `/stage1/api/v1/` |
| systemd | `yino-platform-api` / `yino-voice-agent` | `yino-platform-api-stage1` / `yino-voice-agent-stage1` |
| LiveKit Agent 名 | 生产既有名称 | `yino-customer-service-stage1` |
| 数据 | 生产库 `yino_platform`（勿改） | 同 Docker 实例独立库 `yino_platform_stage1` |

共享但只读复用：

- 生产 LiveKit（`:7880` / `/livekit`）
- 服务器本机已有密钥文件（脚本读取后写入 Stage1 env；不回显、不入库）

## 脚本改造

主脚本：`scripts/deploy_stage1_isolated.py`

必须修改：

1. 本地路径改为 monorepo：
   - `apps/control-plane/api`
   - `apps/runtime/voice-agent`
   - `apps/control-plane/web/dist`
2. 删除任何写入/恢复生产前端的步骤（含历史 `frontend-dist.bak-20260805-...` 恢复逻辑）
3. 保留：仅操作 `/opt/yino-vapi-stage1`、Stage1 systemd、nginx `/stage1` 片段
4. 验收 curl 增加 Stage1 列表接口探测：
   - `GET /stage1/api/v1/customer-services` 不得为 404
5. 验收同时确认生产未被动：
   - 生产首页仍可用
   - 生产 `GET/POST /api/v1/customer-services` 仍为 404（当前回滚后基线）

前端 Stage1 构建参数（本地构建，再上传 dist）：

```text
VITE_BASE_URL=/stage1/
VITE_PLATFORM_API_BASE=/stage1
```

建议提供配套 CMD 说明或薄封装脚本，明确“先 build、再 deploy”，且凭据只从本机环境变量 `BT_HOST` / `BT_USER` / `BT_PASSWORD` 读取。

## 整理工作（部署前，仍不 commit）

- 更新 `PROJECT_STATUS.md`：主仓库为 yinovoice；A1/A2 仅本地/Stage1；生产未启用
- 更新 `TASKS.md`：增加 Stage1 验收与后续提交项
- 补充简短 Stage1 操作说明（CMD）
- 不移动、不删除用户既有未提交改动之外的无关文件

## 验收标准

部署完成后须同时满足：

1. `https://8.215.80.82/` → 200（生产仍在）
2. 生产 `GET /api/v1/customer-services` → 404
3. 生产 `POST /api/v1/customer-services` → 404
4. `https://8.215.80.82/stage1/` → 200
5. Stage1 `GET /api/v1/customer-services` → 非 404（通常 200，空列表亦可）
6. `yino-platform-api-stage1` / `yino-voice-agent-stage1` → active
7. 生产 `yino-platform-api` / `yino-voice-agent` / `yino-livekit` → 仍为 active
8. 生产回滚备份目录仍存在、未被脚本删除

可选冒烟（网页）：

- Stage1 登录 `demo` / `demo123`
- 「我的实例」可加载列表；可新建实例并进入配置页

## 提交策略（部署验收后，需用户另授）

建议在 Stage1 冒烟通过后，由用户明确授权再提交。推荐拆分：

1. 迁移治理文档与规则
2. A1（列表与实例选择）
3. A2（创建与 demo seed）
4. Stage1 部署脚本与说明

在用户说“提交”之前，Agent 不得 commit / push。

## 风险与回退

| 风险 | 缓解 |
|------|------|
| 误写生产目录 | 脚本硬编码仅写 `REMOTE_ROOT=/opt/yino-vapi-stage1`；禁止恢复生产前端 |
| 前端打到生产 API | Stage1 构建强制 `/stage1` base 与 API base |
| 污染生产数据库 | Stage1 不写入生产 `DATABASE_URL` |
| nginx 配置失败 | `nginx -t` 失败则中止 reload |
| Stage1 失败 | 停用 Stage1 systemd + 移除 `/stage1` nginx 片段即可；生产保持不动 |

## 明确不做

- 不轮换或打印服务器密钥
- 不创建生产实例、不删生产实例
- 不覆盖 `E:\YinoVapi\.worktrees\...` 旧项目
- 不把 `deploy/src` 当作本轮真源去“修好再部署”
