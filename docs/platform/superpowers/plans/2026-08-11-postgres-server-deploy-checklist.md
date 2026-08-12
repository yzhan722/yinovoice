# PostgreSQL MVP — 服务器部署清单

> 日期：2026-08-11  
> 范围：把本机已验证的 Postgres 持久化接到 Demo/服务器（如 `8.215.80.82`）。  
> 前提：本机 Task 1–4 已完成；**线上尚未部署数据库**。

## 0. 部署前确认

- [ ] 产品确认：Demo 阶段是否接受「单机 Docker Postgres」过渡（推荐短期），还是直接上大陆托管 RDS。
- [ ] 确认数据落在 **中国大陆** 地域；备份与日志不跨境。
- [ ] 准备强密码（勿使用本机开发密码 `yino/yino`）。
- [ ] 确认 `platform-api` 新代码已上传/同步到服务器（含 `migrations/`、`db/`、`repositories/postgres/`）。
- [ ] 确认未提交 `.env.local` / 真实 `DATABASE_URL`。

## 1. 服务器侧 Postgres（过渡：Docker）

在部署机（与 `yino-platform-api` 同机或同内网）执行：

```bat
REM 示例：服务器上已有 docker / compose
cd /d /opt/yino-vapi
docker compose up -d postgres
docker compose ps
```

建议生产 compose 相对本机改动：

- [ ] `POSTGRES_PASSWORD` 改为强密码（环境变量注入，不写进 git）
- [ ] **不要**把 `5432` 暴露到公网；仅 `127.0.0.1:5432` 或 Docker 内网
- [ ] volume 持久化目录纳入备份策略
- [ ] `restart: unless-stopped`

示例端口绑定（仅本机）：

```yaml
ports:
  - "127.0.0.1:5433:5432"
# 注意：本机 Demo 服务器上 5432 可能已被其他项目占用，Yino 使用 5433。
```

## 1b. 可选：大陆托管 PostgreSQL

若不用 Docker 库：

- [ ] 创建 PG 16/17 实例（大陆可用区）
- [ ] 白名单仅允许 API 所在机器私网/安全组
- [ ] 开启自动备份与时间点恢复；记下 RPO/RTO
- [ ] 拿到连接串，改成 asyncpg 形式：  
  `postgresql+asyncpg://USER:PASS@HOST:5432/DBNAME`

## 2. 配置 platform-api

在服务器 `platform-api` 运行环境（systemd Environment / `.env.local`，勿提交）：

```dotenv
DATABASE_URL=postgresql+asyncpg://USER:PASS@127.0.0.1:5432/yino_platform
```

- [ ] 其余 LiveKit 等现有变量保持不变
- [ ] 未设置 `DATABASE_URL` 时会回退内存——部署验收时务必确认已设置

## 3. 安装依赖与迁移

```bat
cd /d /opt/yino-vapi/platform-api
REM 使用现有 venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
set DATABASE_URL=postgresql+asyncpg://USER:PASS@127.0.0.1:5432/yino_platform
.venv\Scripts\alembic.exe upgrade head
```

Linux 服务器则用：

```bash
cd /opt/yino-vapi/platform-api
.venv/bin/pip install -e .
export DATABASE_URL='postgresql+asyncpg://USER:PASS@127.0.0.1:5432/yino_platform'
.venv/bin/alembic upgrade head
```

- [x] `alembic upgrade head` 成功（2026-08-11，端口 **5433**）
- [x] 库中存在五表：`tenants` / `agent_template_versions` / `voice_agent_instances` / `call_records` / `call_messages`

## 4. 重启 API 并验收

```bash
systemctl restart yino-platform-api
systemctl is-active yino-platform-api
```

验收：

- [x] `GET /health` → `{"status":"ok"}`
- [x] `GET /api/v1/customer-services/{DEMO_ID}` + `X-Tenant-ID` 返回 Demo 配置（含 platform/tenant prompt）
- [x] `PUT` 修改 `display_name` 后 **`systemctl restart yino-platform-api`**，再 GET 名称仍在
- [x] `POST /api/v1/call-records` 写入 transcript 后重启，详情仍在
- [ ] 网页端再打一通真实电话做人工确认（可选）
- [ ] 错误 Tenant 读同一资源 → 404（可选回归）
- [x] 录音文件仍在磁盘目录配置（库内无音频 BLOB）

## 5. 回滚预案

- [ ] 去掉 / 注释 `DATABASE_URL` 并重启 → 回退内存模式（数据不在库则丢失进程内数据）
- [ ] 或 `alembic downgrade -1`（慎用；先备份）
- [ ] Docker volume / RDS 快照备份点已记录

## 6. 明确不做（本轮）

- 不上 Redis / Kafka / Mongo / pgvector
- 不把录音文件塞进数据库
- 不开放 Postgres 公网端口
- 不在本轮建设 `callback_tasks` 等第二轮表
- 不把 `X-Tenant-ID` 当作生产安全边界（仍需后续真实认证）

## 7. 本机对照（已验证时勾选）

- [x] 本机 `docker compose up -d` + `alembic upgrade head`
- [x] 本机冒烟脚本：`python scripts/smoke_postgres_persistence.py` → `SMOKE_PASS`（2026-08-11）
