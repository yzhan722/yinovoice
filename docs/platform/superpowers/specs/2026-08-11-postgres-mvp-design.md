# PostgreSQL MVP 设计规格

> 日期：2026-08-11  
> 范围：`platform-api` 持久化地基；不改前端契约；不引入 Redis/Kafka/ClickHouse/MongoDB/微服务拆库；不上 pgvector（继续 RAGFlow）。  
> 依据：用户确认的 MVP 取舍 + `docs/research/database-architecture-for-demo.md` + 当前 `CustomerServiceRepository` / `CallRecordRepository`。

## 1. 目标

做一个**足够真实、不过度建设**的 PostgreSQL MVP，立即解决：

- 服务重启后实例配置与通话/Transcript 不丢失
- Tenant 隔离由数据库约束保证（复合外键 + 显式 `tenant_id` 查询）
- 现有 API / 前端无需大改：继续走 Repository Protocol

非目标（第二轮或更后）：

- `callback_tasks` / `appointment_results` / `knowledge_documents` / `audit_events`
- RLS（本轮可预留 `app.tenant_id` 用法说明，但不作为首轮验收）
- 录音/知识原文件进库（继续本地目录/对象存储元数据；库内无音频 BLOB）
- 完整 SaaS 成员/RBAC、独立向量库

## 2. 技术选型

| 项 | 选择 |
|---|---|
| 数据库 | PostgreSQL 16/17（本地 Compose 固定 17） |
| ORM/驱动 | SQLAlchemy 2.x async + `asyncpg` |
| 迁移 | Alembic |
| 本地 | Docker Compose + 命名 volume |
| 访问边界 | 保留现有 Protocol；新增 Postgres Adapter |
| 配置 | `DATABASE_URL`；未配置时默认仍用内存仓储（测试/无库开发不破） |

## 3. 第一轮五张表

### 3.1 `tenants`

- `id uuid PK`
- `name varchar(120) NOT NULL`
- `home_region text NOT NULL DEFAULT 'cn-mainland'`
- `status text NOT NULL CHECK (status IN ('active','disabled'))`
- `created_at` / `updated_at timestamptz`

种子：Demo Tenant `00000000-0000-0000-0000-000000000001`。

### 3.2 `agent_template_versions`

平台级不可变模板发布版本（最小可用）：

- `id uuid PK`
- `template_key text NOT NULL`（如 `pacific-dental-demo`）
- `version integer NOT NULL CHECK (version >= 1)`
- `schema_version integer NOT NULL DEFAULT 1`
- `package jsonb NOT NULL`（模板元数据/默认包；发布后只读）
- `published_at timestamptz NOT NULL`
- `UNIQUE (template_key, version)`

种子：一条 Demo template version，供实例 FK 绑定。

### 3.3 `voice_agent_instances`

映射现有 `CustomerServiceInstance`（API 名不变）：

| 列 | 说明 |
|---|---|
| `id`, `tenant_id` | `UNIQUE (tenant_id, id)`；`tenant_id → tenants` |
| `template_version_id` | → `agent_template_versions.id` |
| `version` | 乐观锁，`CHECK (version >= 1)` |
| `display_name`, `organization_name`, `business_profile`, `primary_language`, `greeting` | 正规列 |
| `platform_prompt`, `tenant_prompt` | 正规列（已上线双 Prompt，不塞进 jsonb） |
| `voice_config jsonb`, `response_config jsonb` | Voice/Response Profile |
| `created_at`, `updated_at` | timestamptz |

更新必须原子 CAS（Adapter 内）：

```sql
UPDATE voice_agent_instances
SET ... , version = :new_version, updated_at = now()
WHERE tenant_id = :tenant_id AND id = :id AND version = :expected_version
RETURNING *;
```

其中 `expected_version = new_version - 1`（路由层已算出 `new_version`）。0 行时由上层区分 404/409（先 get，再 save；save 失败则 409）。

### 3.4 `call_records`

映射 `CallRecord`（不含 messages 内嵌）：

- 正规列：`id`, `tenant_id`, `voice_agent_instance_id`, `room_name`, `status`, `direction`, `started_at`, `ended_at`, `duration_sec`, `created_at`
- 录音元数据列：`recording_status`, `recording_mime_type`, `recording_size_bytes`, `recording_failure_code`（与现领域一致；无 object_key 则本轮不加）
- `UNIQUE (tenant_id, id)`
- `FOREIGN KEY (tenant_id, voice_agent_instance_id) REFERENCES voice_agent_instances (tenant_id, id)`
- `CHECK (ended_at >= started_at)`
- 索引 `(tenant_id, created_at DESC, id DESC)`

### 3.5 `call_messages`

- `PRIMARY KEY (tenant_id, call_record_id, sequence)`
- `role`, `text`, `created_at`
- `FOREIGN KEY (tenant_id, call_record_id) REFERENCES call_records (tenant_id, id) ON DELETE CASCADE`

`CallRecord.save` 在同一事务：upsert 记录后，**替换**该通话的 messages（删除旧行再插入），保持与当前“整份 record 覆盖保存”语义一致。

## 4. Repository 边界

不改 Protocol 方法签名：

```python
class CustomerServiceRepository(Protocol):
    async def get(self, instance_id: UUID, tenant_id: UUID) -> CustomerServiceInstance | None: ...
    async def save(self, instance: CustomerServiceInstance) -> CustomerServiceInstance: ...

class CallRecordRepository(Protocol):
    async def save(self, record: CallRecord) -> CallRecord: ...
    async def list_for_tenant(self, tenant_id: UUID, *, limit: int, offset: int) -> tuple[list[CallRecord], int]: ...
    async def get(self, record_id: UUID, tenant_id: UUID) -> CallRecord | None: ...
```

新增：

- `repositories/postgres/customer_services.py`
- `repositories/postgres/call_records.py`
- `db/engine.py`, `db/models.py`, `db/seed.py`

`create_app`：若 `DATABASE_URL` 非空 → Postgres adapters + 启动时确保 Demo 种子存在；否则保持 `InMemory*`（现有测试零改动可跑）。

## 5. 取舍（锁定）

1. `voice_config` / `response_config` / template `package` 用 jsonb；Tenant、状态、时间、外键、版本、Prompt 正文用正规列。
2. Transcript 拆 `call_messages`，禁止整段 transcript 大 JSON。
3. 预约权威仍在外部系统；本轮**不**建预约权威表（第二轮 `appointment_results` 只存执行结果）。
4. 知识检索继续 RAGFlow；不上 pgvector。
5. 不引入 Redis、Kafka、ClickHouse、MongoDB、拆库。
6. 录音文件仍在 `CALL_RECORDING_DIR`；数据库只存状态/MIME/大小等已有字段。

## 6. 验收

- `docker compose up -d` 后 `alembic upgrade head` 成功。
- 配置 `DATABASE_URL` 启动 API：重启后 Demo 实例配置仍在；PUT 更新后持久化。
- 创建通话记录 + messages 后重启仍可列表/详情展示完整 Transcript。
- 跨 Tenant 复合外键插入失败；`get` 带错误 Tenant 返回空（API 404）。
- 两并发相同 `expected_version` 更新：仅一个成功，另一个 409。
- 未设置 `DATABASE_URL` 时现有 pytest 全绿。

## 7. 实施顺序

1. Compose + 依赖 + `DATABASE_URL` + Alembic + 五表迁移 + 种子  
2. 两个 Postgres Repository Adapter + 集成测试  
3. `create_app` 按配置切换；可选 `/health` 增加 db 探测（不破坏现有 `{status:ok}` 时可另开字段）

第二轮（本规格之外）：前端 mock → `callback_tasks` / `appointment_results` / `knowledge_documents` / `audit_events`。
